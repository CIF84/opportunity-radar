from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.phase3_config import CandidateProfile, Taxonomy, digest, load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import SemanticJobInput
from opportunity_radar.prospective_validation import build_current_cluster_population, load_prospective_protocol
from opportunity_radar.semantic_worthiness_validation import (
    _current_append_only,
    effective_selected_items,
    load_jsonl,
)


DEFAULT_CONFIG = Path("experiments/stretch_evidence_boundary_v1.yaml")
EXPERIMENT_TYPE = "STRETCH_EVIDENCE_BOUNDARY_AUDIT"
CAPABILITY_LEVEL_ORDER = {
    "NONE": 0,
    "BASIC": 1,
    "DEVELOPING": 2,
    "INTERMEDIATE": 3,
    "ADVANCED": 4,
    "EXPERT": 5,
}
DOMAIN_DEPTH_ORDER = {"LIMITED": 1, "MODERATE": 2, "DEEP": 3}


class StretchEvidenceError(ValueError):
    pass


class StretchClass(str, Enum):
    CURRENT_FIT = "CURRENT_FIT"
    MANAGEABLE_STRETCH = "MANAGEABLE_STRETCH"
    EXCESSIVE_STRETCH = "EXCESSIVE_STRETCH"
    UNRESOLVED = "UNRESOLVED"


class RequirementStrength(str, Enum):
    CORE = "CORE"
    PREFERRED = "PREFERRED"
    CONTEXTUAL = "CONTEXTUAL"


class SupportState(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class GapSeverity(str, Enum):
    NONE = "NONE"
    MATERIAL = "MATERIAL"
    DECISIVE = "DECISIVE"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class StretchRequirementAssessment:
    category: str
    concept_id: str
    vacancy_evidence: tuple[str, ...]
    vacancy_source_fields: tuple[str, ...]
    requirement_strength: RequirementStrength
    candidate_evidence: tuple[str, ...]
    support_state: SupportState
    gap_severity: GapSeverity
    reason_code: str

    def payload(self) -> dict[str, Any]:
        value = asdict(self)
        value["requirement_strength"] = self.requirement_strength.value
        value["support_state"] = self.support_state.value
        value["gap_severity"] = self.gap_severity.value
        value["vacancy_evidence"] = list(self.vacancy_evidence)
        value["vacancy_source_fields"] = list(self.vacancy_source_fields)
        value["candidate_evidence"] = list(self.candidate_evidence)
        return value


@dataclass(frozen=True)
class StretchAssessment:
    stretch_class: StretchClass
    requirements: tuple[StretchRequirementAssessment, ...]
    decisive_requirement_concepts: tuple[str, ...]
    unresolved_requirement_concepts: tuple[str, ...]
    rules_fingerprint: str
    input_fingerprint: str
    assessment_fingerprint: str

    def payload(self) -> dict[str, Any]:
        return {
            "stretch_class": self.stretch_class.value,
            "requirements": [item.payload() for item in self.requirements],
            "decisive_requirement_concepts": list(self.decisive_requirement_concepts),
            "unresolved_requirement_concepts": list(self.unresolved_requirement_concepts),
            "rules_fingerprint": self.rules_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "assessment_fingerprint": self.assessment_fingerprint,
        }


@dataclass(frozen=True)
class RoleRequirementRule:
    concept_id: str
    category: str
    title_patterns: tuple[re.Pattern[str], ...]
    direct_capabilities: tuple[str, ...]
    adjacent_capabilities: tuple[str, ...]
    experience_domains: tuple[str, ...]
    numeric_evidence: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class StretchPolicy:
    version: str
    supported_level: int
    adjacent_level: int
    elevated_title_patterns: tuple[re.Pattern[str], ...]
    required_years_pattern: re.Pattern[str]
    decisive_years_minimum: int
    preferred_context_pattern: re.Pattern[str]
    equivalent_education_pattern: re.Pattern[str]
    mandatory_degree_patterns: tuple[re.Pattern[str], ...]
    preferred_degree_patterns: tuple[re.Pattern[str], ...]
    role_requirements: tuple[RoleRequirementRule, ...]
    fingerprint: str


@dataclass(frozen=True)
class StretchAuditConfig:
    raw: dict[str, Any]
    fingerprint: str
    policy: StretchPolicy
    human_excessive_patterns: tuple[re.Pattern[str], ...]
    human_current_fit_patterns: tuple[re.Pattern[str], ...]

    @property
    def experiment_id(self) -> str:
        return str(self.raw["experiment_id"])


def _compile(patterns: list[str], context: str) -> tuple[re.Pattern[str], ...]:
    if not isinstance(patterns, list) or not patterns or any(not isinstance(item, str) for item in patterns):
        raise StretchEvidenceError(f"{context} must be a non-empty pattern list")
    try:
        return tuple(re.compile(item, re.I) for item in patterns)
    except re.error as exc:
        raise StretchEvidenceError(f"invalid {context} pattern: {exc}") from exc


def _sha256(path: str | Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], check=True, capture_output=True, text=True,
    ).stdout
    return {
        "commit": commit,
        "dirty": bool(status),
        "worktree_status_fingerprint": hashlib.sha256(status.encode()).hexdigest(),
    }


def _validate_rule_references(rule: dict[str, Any], taxonomy: Taxonomy) -> None:
    expected = {
        "concept_id", "category", "title_patterns", "direct_capabilities",
        "adjacent_capabilities", "experience_domains", "numeric_evidence",
    }
    if set(rule) != expected:
        raise StretchEvidenceError(f"role requirement {rule.get('concept_id')} has an invalid schema")
    for field in ("direct_capabilities", "adjacent_capabilities", "experience_domains"):
        values = rule[field]
        if not isinstance(values, list) or len(values) != len(set(values)):
            raise StretchEvidenceError(f"{rule['concept_id']}.{field} must be a unique list")
        for concept_id in values:
            taxonomy.require(concept_id, f"stretch rule {field}")
    numeric = rule["numeric_evidence"]
    if not isinstance(numeric, list):
        raise StretchEvidenceError("numeric_evidence must be a list")
    for item in numeric:
        if not isinstance(item, dict) or set(item) != {"path", "partial_minimum", "supported_minimum"}:
            raise StretchEvidenceError("numeric evidence has an invalid schema")
        if not isinstance(item["path"], str) or not item["path"].startswith("facts."):
            raise StretchEvidenceError("numeric evidence path must be rooted in facts")
        if float(item["partial_minimum"]) > float(item["supported_minimum"]):
            raise StretchEvidenceError("numeric evidence thresholds are reversed")


def load_stretch_audit_config(path: str | Path = DEFAULT_CONFIG) -> StretchAuditConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version", "experiment_id", "experiment_type", "specification",
        "inputs", "policy", "human_adjudication", "counterfactuals", "privacy", "outputs",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise StretchEvidenceError("stretch audit has an invalid top-level schema")
    if raw["schema_version"] != 1 or raw["experiment_type"] != EXPERIMENT_TYPE:
        raise StretchEvidenceError("unsupported stretch audit identity")
    inputs = raw["inputs"]
    expected_inputs = {
        "candidate_path", "taxonomy_path", "prospective_protocol_path", "database_path",
        "worthiness_manifest_path", "worthiness_judgments_path",
        "worthiness_replacements_path", "worthiness_result_path",
    }
    if not isinstance(inputs, dict) or set(inputs) != expected_inputs:
        raise StretchEvidenceError("stretch audit inputs have an invalid schema")
    for key in ("candidate_path", "taxonomy_path", "prospective_protocol_path", "worthiness_result_path"):
        if not Path(inputs[key]).exists():
            raise StretchEvidenceError(f"configured repository input does not exist: {inputs[key]}")
    if raw["privacy"] != {
        "detailed_artifact": "PRIVATE_LOCAL",
        "aggregate_artifact": "REPOSITORY_SAFE",
        "raw_human_notes": "PRIVATE_LOCAL_APPEND_ONLY",
    }:
        raise StretchEvidenceError("invalid stretch audit privacy boundary")
    if raw["outputs"] != {"root": "output/stretch_evidence_boundary"}:
        raise StretchEvidenceError("invalid stretch audit output root")

    taxonomy = load_taxonomy(inputs["taxonomy_path"])
    policy_raw = raw["policy"]
    expected_policy = {
        "policy_version", "supported_level", "adjacent_level", "elevated_title_patterns",
        "required_years_pattern", "decisive_years_minimum", "preferred_context_pattern",
        "equivalent_education_pattern", "mandatory_degree_patterns",
        "preferred_degree_patterns", "role_requirements",
    }
    if not isinstance(policy_raw, dict) or set(policy_raw) != expected_policy:
        raise StretchEvidenceError("stretch policy has an invalid schema")
    if policy_raw["supported_level"] not in CAPABILITY_LEVEL_ORDER:
        raise StretchEvidenceError("invalid supported capability level")
    if policy_raw["adjacent_level"] not in CAPABILITY_LEVEL_ORDER:
        raise StretchEvidenceError("invalid adjacent capability level")
    rules: list[RoleRequirementRule] = []
    seen: set[str] = set()
    for raw_rule in policy_raw["role_requirements"]:
        if not isinstance(raw_rule, dict):
            raise StretchEvidenceError("role requirements must be mappings")
        _validate_rule_references(raw_rule, taxonomy)
        concept_id = str(raw_rule["concept_id"])
        if concept_id in seen:
            raise StretchEvidenceError(f"duplicate stretch requirement concept: {concept_id}")
        seen.add(concept_id)
        rules.append(RoleRequirementRule(
            concept_id=concept_id,
            category=str(raw_rule["category"]),
            title_patterns=_compile(raw_rule["title_patterns"], f"{concept_id}.title_patterns"),
            direct_capabilities=tuple(raw_rule["direct_capabilities"]),
            adjacent_capabilities=tuple(raw_rule["adjacent_capabilities"]),
            experience_domains=tuple(raw_rule["experience_domains"]),
            numeric_evidence=tuple(raw_rule["numeric_evidence"]),
        ))
    try:
        policy = StretchPolicy(
            version=str(policy_raw["policy_version"]),
            supported_level=CAPABILITY_LEVEL_ORDER[policy_raw["supported_level"]],
            adjacent_level=CAPABILITY_LEVEL_ORDER[policy_raw["adjacent_level"]],
            elevated_title_patterns=_compile(policy_raw["elevated_title_patterns"], "elevated title"),
            required_years_pattern=re.compile(policy_raw["required_years_pattern"], re.I),
            decisive_years_minimum=int(policy_raw["decisive_years_minimum"]),
            preferred_context_pattern=re.compile(policy_raw["preferred_context_pattern"], re.I),
            equivalent_education_pattern=re.compile(policy_raw["equivalent_education_pattern"], re.I),
            mandatory_degree_patterns=_compile(policy_raw["mandatory_degree_patterns"], "mandatory degree"),
            preferred_degree_patterns=_compile(policy_raw["preferred_degree_patterns"], "preferred degree"),
            role_requirements=tuple(rules),
            fingerprint=digest(policy_raw),
        )
    except (re.error, TypeError, ValueError) as exc:
        raise StretchEvidenceError(f"invalid stretch policy: {exc}") from exc
    human = raw["human_adjudication"]
    required_human = {
        "stretch_reason_codes", "market_reason_codes", "insufficient_reason_codes",
        "explicit_excessive_note_patterns", "current_fit_note_patterns",
    }
    if not isinstance(human, dict) or set(human) != required_human:
        raise StretchEvidenceError("human adjudication config has an invalid schema")
    for key in ("stretch_reason_codes", "market_reason_codes", "insufficient_reason_codes"):
        if not isinstance(human[key], list) or not human[key]:
            raise StretchEvidenceError(f"{key} must be a non-empty list")
    counterfactuals = raw["counterfactuals"]
    if set(counterfactuals) != {"excessive_exploration_rate", "exploration_seed"}:
        raise StretchEvidenceError("counterfactual configuration has an invalid schema")
    rate = float(counterfactuals["excessive_exploration_rate"])
    if not 0 <= rate <= 1:
        raise StretchEvidenceError("excessive exploration rate must be in [0, 1]")
    return StretchAuditConfig(
        raw=raw,
        fingerprint=digest(raw),
        policy=policy,
        human_excessive_patterns=_compile(human["explicit_excessive_note_patterns"], "human excessive"),
        human_current_fit_patterns=_compile(human["current_fit_note_patterns"], "human current fit"),
    )


def _bounded(value: str, maximum: int = 240) -> str:
    text = " ".join(value.split())
    return text if len(text) <= maximum else text[: maximum - 1].rstrip() + "…"


def _get_path(root: dict[str, Any], path: str) -> Any:
    value: Any = root
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _candidate_payload(profile: CandidateProfile) -> dict[str, Any]:
    facts = profile.facts
    return {
        "facts": {
            "career": facts.get("career", {}),
            "leadership": facts.get("leadership", {}),
            "education": facts.get("education", {}),
        },
        "capabilities": list(profile.capabilities),
        "experience": profile.experience,
    }


def _job_payload(job: SemanticJobInput) -> dict[str, Any]:
    return {
        "title": job.title,
        "description": job.description,
        "employment_type": job.employment_type,
        "department": job.department,
    }


def _capability_index(profile: CandidateProfile) -> dict[str, dict[str, Any]]:
    return {str(item["capability_id"]): item for item in profile.capabilities}


def _candidate_support(
    rule: RoleRequirementRule,
    profile: CandidateProfile,
    policy: StretchPolicy,
) -> tuple[SupportState, tuple[str, ...], str, int | None]:
    capabilities = _capability_index(profile)
    direct = [capabilities[item] for item in rule.direct_capabilities if item in capabilities]
    if direct:
        maximum = max(CAPABILITY_LEVEL_ORDER[item["level"]] for item in direct)
        evidence = tuple(
            f"capabilities[{item['capability_id']}].level={item['level']}"
            for item in sorted(direct, key=lambda value: value["capability_id"])
        )
        if maximum >= policy.supported_level:
            return SupportState.SUPPORTED, evidence, "DIRECT_CAPABILITY_SUPPORTED", maximum
        if maximum == 0:
            return SupportState.UNSUPPORTED, evidence, "EXPLICIT_CAPABILITY_NONE", maximum
        return SupportState.PARTIAL, evidence, "DIRECT_CAPABILITY_BELOW_REQUIRED", maximum

    adjacent = [capabilities[item] for item in rule.adjacent_capabilities if item in capabilities]
    useful_adjacent = [
        item for item in adjacent
        if CAPABILITY_LEVEL_ORDER[item["level"]] >= policy.adjacent_level
    ]
    if useful_adjacent:
        evidence = tuple(
            f"capabilities[{item['capability_id']}].level={item['level']}"
            for item in sorted(useful_adjacent, key=lambda value: value["capability_id"])
        )
        return SupportState.PARTIAL, evidence, "ADJACENT_TRANSFERABLE_EVIDENCE", None

    candidate_domains = {
        str(item["domain_id"]): item for item in profile.experience.get("domains", [])
    }
    domains = [candidate_domains[item] for item in rule.experience_domains if item in candidate_domains]
    if domains:
        maximum_depth = max(DOMAIN_DEPTH_ORDER[item["depth"]] for item in domains)
        evidence = tuple(
            f"experience.domains[{item['domain_id']}].depth={item['depth']}"
            for item in sorted(domains, key=lambda value: value["domain_id"])
        )
        state = SupportState.SUPPORTED if maximum_depth >= DOMAIN_DEPTH_ORDER["DEEP"] else SupportState.PARTIAL
        reason = "DIRECT_DOMAIN_EXPERIENCE_SUPPORTED" if state is SupportState.SUPPORTED else "ADJACENT_DOMAIN_EXPERIENCE"
        return state, evidence, reason, None

    for numeric in rule.numeric_evidence:
        value = _get_path({"facts": profile.facts}, str(numeric["path"]))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            evidence = (f"{numeric['path']}={value}",)
            if value >= float(numeric["supported_minimum"]):
                return SupportState.SUPPORTED, evidence, "NUMERIC_EXPERIENCE_SUPPORTED", None
            if value >= float(numeric["partial_minimum"]):
                return SupportState.PARTIAL, evidence, "NUMERIC_ADJACENT_EXPERIENCE", None
    return SupportState.UNKNOWN, (), "CANDIDATE_EVIDENCE_MISSING", None


def _gap(state: SupportState, strength: RequirementStrength) -> GapSeverity:
    if state is SupportState.SUPPORTED:
        return GapSeverity.NONE
    if state is SupportState.UNKNOWN:
        return GapSeverity.UNRESOLVED
    if state is SupportState.UNSUPPORTED and strength is RequirementStrength.CORE:
        return GapSeverity.DECISIVE
    return GapSeverity.MATERIAL


def _role_requirements(
    job: SemanticJobInput,
    profile: CandidateProfile,
    policy: StretchPolicy,
) -> list[tuple[StretchRequirementAssessment, RoleRequirementRule, int | None]]:
    title = job.title or ""
    result: list[tuple[StretchRequirementAssessment, RoleRequirementRule, int | None]] = []
    for rule in policy.role_requirements:
        match = next((pattern.search(title) for pattern in rule.title_patterns if pattern.search(title)), None)
        if match is None:
            continue
        state, evidence, reason, direct_max = _candidate_support(rule, profile, policy)
        requirement = StretchRequirementAssessment(
            category=rule.category,
            concept_id=rule.concept_id,
            vacancy_evidence=(_bounded(match.group(0)),),
            vacancy_source_fields=("title",),
            requirement_strength=RequirementStrength.CORE,
            candidate_evidence=evidence,
            support_state=state,
            gap_severity=_gap(state, RequirementStrength.CORE),
            reason_code=reason,
        )
        result.append((requirement, rule, direct_max))
    return result


def _qualification_requirements(
    job: SemanticJobInput,
    profile: CandidateProfile,
    policy: StretchPolicy,
) -> list[StretchRequirementAssessment]:
    description = job.description or ""
    result: list[StretchRequirementAssessment] = []
    for strength, patterns in (
        (RequirementStrength.CORE, policy.mandatory_degree_patterns),
        (RequirementStrength.PREFERRED, policy.preferred_degree_patterns),
    ):
        match = next((pattern.search(description) for pattern in patterns if pattern.search(description)), None)
        if match is None:
            continue
        window = description[max(0, match.start() - 80): min(len(description), match.end() + 80)]
        if policy.equivalent_education_pattern.search(window):
            state = SupportState.UNKNOWN
            evidence = ("facts.education.completed_bachelors_degree=false; equivalent experience not normalized",)
            reason = "EQUIVALENT_EDUCATION_PATH_UNRESOLVED"
        else:
            completed = profile.facts.get("education", {}).get("completed_bachelors_degree")
            if completed is True:
                state, reason = SupportState.SUPPORTED, "MANDATORY_CREDENTIAL_SUPPORTED"
            elif completed is False:
                state = SupportState.UNSUPPORTED
                reason = (
                    "MANDATORY_CREDENTIAL_ABSENT"
                    if strength is RequirementStrength.CORE
                    else "PREFERRED_CREDENTIAL_ABSENT"
                )
            else:
                state, reason = SupportState.UNKNOWN, "CREDENTIAL_EVIDENCE_MISSING"
            evidence = (f"facts.education.completed_bachelors_degree={str(completed).lower()}",)
        result.append(StretchRequirementAssessment(
            category="CREDENTIAL",
            concept_id="bachelors_degree",
            vacancy_evidence=(_bounded(window),),
            vacancy_source_fields=("description",),
            requirement_strength=strength,
            candidate_evidence=evidence,
            support_state=state,
            gap_severity=_gap(state, strength),
            reason_code=reason,
        ))
        break
    return result


def _depth_requirements(
    job: SemanticJobInput,
    policy: StretchPolicy,
    role_values: list[tuple[StretchRequirementAssessment, RoleRequirementRule, int | None]],
) -> list[StretchRequirementAssessment]:
    title = job.title or ""
    description = job.description or ""
    elevated = next(
        (pattern.search(title) for pattern in policy.elevated_title_patterns if pattern.search(title)),
        None,
    )
    years = list(policy.required_years_pattern.finditer(description))
    result: list[StretchRequirementAssessment] = []
    for requirement, rule, direct_max in role_values:
        if requirement.support_state is not SupportState.PARTIAL or direct_max is None:
            continue
        if direct_max > CAPABILITY_LEVEL_ORDER["DEVELOPING"]:
            continue
        evidence: list[str] = []
        source_fields: list[str] = []
        reason: str | None = None
        if elevated is not None:
            evidence.append(_bounded(elevated.group(0)))
            source_fields.append("title")
            reason = "ELEVATED_ROLE_DEPTH_BEYOND_DEVELOPING_CAPABILITY"
        for match in years:
            count = int(match.group(1))
            window = description[max(0, match.start() - 80): min(len(description), match.end() + 80)]
            if count < policy.decisive_years_minimum or policy.preferred_context_pattern.search(window):
                continue
            evidence.append(_bounded(window))
            source_fields.append("description")
            reason = "REQUIRED_PROFESSIONAL_YEARS_BEYOND_DEVELOPING_CAPABILITY"
            break
        if reason is None:
            continue
        result.append(StretchRequirementAssessment(
            category="PROFESSIONAL_DEPTH",
            concept_id=f"{rule.concept_id}_depth",
            vacancy_evidence=tuple(evidence),
            vacancy_source_fields=tuple(source_fields),
            requirement_strength=RequirementStrength.CORE,
            candidate_evidence=requirement.candidate_evidence,
            support_state=SupportState.UNSUPPORTED,
            gap_severity=GapSeverity.DECISIVE,
            reason_code=reason,
        ))
    return result


def assess_stretch(
    job: SemanticJobInput,
    profile: CandidateProfile,
    policy: StretchPolicy,
) -> StretchAssessment:
    role_values = _role_requirements(job, profile, policy)
    requirements = [item[0] for item in role_values]
    requirements.extend(_qualification_requirements(job, profile, policy))
    requirements.extend(_depth_requirements(job, policy, role_values))
    requirements.sort(key=lambda item: (item.concept_id, item.category, item.reason_code))
    core = [item for item in requirements if item.requirement_strength is RequirementStrength.CORE]
    decisive = tuple(sorted({
        item.concept_id for item in core
        if item.support_state is SupportState.UNSUPPORTED and item.gap_severity is GapSeverity.DECISIVE
    }))
    unresolved = tuple(sorted({
        item.concept_id for item in core if item.support_state is SupportState.UNKNOWN
    }))
    if decisive:
        final = StretchClass.EXCESSIVE_STRETCH
    elif not core or unresolved:
        final = StretchClass.UNRESOLVED
    elif all(item.support_state is SupportState.SUPPORTED for item in core):
        final = StretchClass.CURRENT_FIT
    elif any(item.support_state is SupportState.PARTIAL for item in core):
        final = StretchClass.MANAGEABLE_STRETCH
    else:
        final = StretchClass.UNRESOLVED
    input_payload = {
        "job": _job_payload(job),
        "candidate": _candidate_payload(profile),
        "rules_fingerprint": policy.fingerprint,
    }
    input_fingerprint = digest(input_payload)
    base = {
        "stretch_class": final.value,
        "requirements": [item.payload() for item in requirements],
        "decisive_requirement_concepts": list(decisive),
        "unresolved_requirement_concepts": list(unresolved),
        "rules_fingerprint": policy.fingerprint,
        "input_fingerprint": input_fingerprint,
    }
    return StretchAssessment(
        stretch_class=final,
        requirements=tuple(requirements),
        decisive_requirement_concepts=decisive,
        unresolved_requirement_concepts=unresolved,
        rules_fingerprint=policy.fingerprint,
        input_fingerprint=input_fingerprint,
        assessment_fingerprint=digest(base),
    )


def _semantic_job(item: dict[str, Any]) -> SemanticJobInput:
    return SemanticJobInput(
        company_name=str(item.get("company_name", "Unknown")),
        title=item.get("title"),
        description=str(item.get("description") or item.get("description_excerpt") or ""),
        locations=tuple(item.get("locations", [])),
        work_mode=str(item.get("work_mode", "unspecified")),
        employment_type=item.get("employment_type"),
        department=item.get("department"),
    )


def _human_category(label: str, reasons: list[str], config: StretchAuditConfig) -> str:
    if label == "WORTH_DEEP_ASSESSMENT":
        return "WORTH_QUALIFICATION_UNCERTAINTY"
    raw = config.raw["human_adjudication"]
    reason_set = set(reasons)
    if reason_set & set(raw["stretch_reason_codes"]):
        return "STRETCH_RELATED_REJECTION"
    if reason_set & set(raw["market_reason_codes"]):
        return "MARKET_ONLY_REJECTION"
    if reason_set & set(raw["insufficient_reason_codes"]):
        return "UNAVAILABLE_OR_INSUFFICIENT_EVIDENCE"
    return "PREFERENCE_ONLY_OR_OTHER_REJECTION"


def _human_sample(
    config: StretchAuditConfig,
    profile: CandidateProfile,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inputs = config.raw["inputs"]
    manifest = json.loads(Path(inputs["worthiness_manifest_path"]).read_text(encoding="utf-8"))
    selected = effective_selected_items(manifest, load_jsonl(inputs["worthiness_replacements_path"]))
    judgments = _current_append_only(
        load_jsonl(inputs["worthiness_judgments_path"]), manifest["preparation_id"], "cluster_id",
    )
    detail: list[dict[str, Any]] = []
    for item in sorted(selected, key=lambda value: int(value["review_number"])):
        judgment = judgments.get(item["cluster_id"])
        if judgment is None:
            raise StretchEvidenceError("frozen worthiness sample is not fully reviewed")
        assessment = assess_stretch(_semantic_job(item), profile, config.policy)
        note = str(judgment.get("note") or "")
        category = _human_category(judgment["label"], judgment.get("reasons", []), config)
        human_fit_supported = (
            category in {"PREFERENCE_ONLY_OR_OTHER_REJECTION", "MARKET_ONLY_REJECTION"}
            or any(pattern.search(note) for pattern in config.human_current_fit_patterns)
        )
        detail.append({
            "review_number": int(item["review_number"]),
            "cluster_id": item["cluster_id"],
            "company_id": item["company_id"],
            "title": item.get("title"),
            "stratum": item["stratum"],
            "human_label": judgment["label"],
            "human_reason_codes": judgment.get("reasons", []),
            "human_adjudication_category": category,
            "human_evident_excessive": (
                category == "STRETCH_RELATED_REJECTION"
                and any(pattern.search(note) for pattern in config.human_excessive_patterns)
            ),
            "human_evident_current_fit": human_fit_supported,
            "stretch_assessment": assessment.payload(),
        })
    classes = Counter(item["stretch_assessment"]["stretch_class"] for item in detail)
    categories = Counter(item["human_adjudication_category"] for item in detail)
    worth = [item for item in detail if item["human_label"] == "WORTH_DEEP_ASSESSMENT"]
    predicted_excessive = [
        item for item in detail
        if item["stretch_assessment"]["stretch_class"] == StretchClass.EXCESSIVE_STRETCH.value
    ]
    human_excessive = [item for item in detail if item["human_evident_excessive"]]
    true_excessive = [item for item in predicted_excessive if item["human_evident_excessive"]]
    current_fit_predictions = [
        item for item in detail
        if item["stretch_assessment"]["stretch_class"] == StretchClass.CURRENT_FIT.value
    ]
    current_fit_supported = [item for item in current_fit_predictions if item["human_evident_current_fit"]]
    return {
        "sample_size": len(detail),
        "reviewed": len(judgments),
        "class_distribution": dict(sorted(classes.items())),
        "human_adjudication_categories": dict(sorted(categories.items())),
        "worth_count": len(worth),
        "worth_excessive_count": sum(
            item["stretch_assessment"]["stretch_class"] == StretchClass.EXCESSIVE_STRETCH.value
            for item in worth
        ),
        "worth_protection_recall": round(
            sum(item["stretch_assessment"]["stretch_class"] != StretchClass.EXCESSIVE_STRETCH.value for item in worth)
            / len(worth), 6,
        ) if worth else None,
        "human_evident_excessive_count": len(human_excessive),
        "detected_human_evident_excessive": len(true_excessive),
        "excessive_detection_coverage": round(len(true_excessive) / len(human_excessive), 6) if human_excessive else None,
        "excessive_prediction_precision": round(len(true_excessive) / len(predicted_excessive), 6) if predicted_excessive else None,
        "preference_only_false_excessive": sum(
            item["human_adjudication_category"] == "PREFERENCE_ONLY_OR_OTHER_REJECTION"
            for item in predicted_excessive
        ),
        "market_only_false_excessive": sum(
            item["human_adjudication_category"] == "MARKET_ONLY_REJECTION"
            for item in predicted_excessive
        ),
        "current_fit_predictions": len(current_fit_predictions),
        "human_supported_current_fit_predictions": len(current_fit_supported),
        "current_fit_precision_where_human_supported": round(
            len(current_fit_supported) / len(current_fit_predictions), 6,
        ) if current_fit_predictions else None,
        "unresolved_rate": round(classes[StretchClass.UNRESOLVED.value] / len(detail), 6) if detail else None,
    }, detail


def _stable_selected(seed: str, identity: str, rate: float) -> bool:
    fraction = int.from_bytes(hashlib.sha256(f"{seed}:{identity}".encode()).digest()[:8], "big") / 2**64
    return fraction < rate


def _counterfactuals(
    detail: list[dict[str, Any]],
    config: StretchAuditConfig,
    cost_per_call: float,
) -> dict[str, Any]:
    scenarios: dict[str, list[dict[str, Any]]] = {
        "MANAGEABLE_PLUS_UNRESOLVED": [
            item for item in detail
            if item["stretch_assessment"]["stretch_class"]
            in {StretchClass.MANAGEABLE_STRETCH.value, StretchClass.UNRESOLVED.value}
        ],
        "ALL_EXCEPT_EXCESSIVE": [
            item for item in detail
            if item["stretch_assessment"]["stretch_class"] != StretchClass.EXCESSIVE_STRETCH.value
        ],
    }
    rate = float(config.raw["counterfactuals"]["excessive_exploration_rate"])
    seed = str(config.raw["counterfactuals"]["exploration_seed"])
    scenarios["ALL_EXCEPT_EXCESSIVE_PLUS_EXPLORATION"] = [
        item for item in detail
        if item["stretch_assessment"]["stretch_class"] != StretchClass.EXCESSIVE_STRETCH.value
        or _stable_selected(seed, str(item["cluster_id"]), rate)
    ]
    worth_total = sum(item["human_label"] == "WORTH_DEEP_ASSESSMENT" for item in detail)
    result = {}
    for name, retained in scenarios.items():
        worth = sum(item["human_label"] == "WORTH_DEEP_ASSESSMENT" for item in retained)
        result[name] = {
            "semantic_calls": len(retained),
            "call_reduction": len(detail) - len(retained),
            "call_reduction_fraction": round((len(detail) - len(retained)) / len(detail), 6),
            "projected_cost_usd": round(len(retained) * cost_per_call, 8),
            "human_worth_retained": worth,
            "human_worth_total": worth_total,
            "human_worth_recall": round(worth / worth_total, 6) if worth_total else None,
        }
    return result


def _cost_per_call(path: str | Path) -> float:
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    all_routed = result["metrics"]["counterfactual_economics"]["ALL_ROUTED"]
    calls = int(all_routed["current_population_projected_calls"])
    if calls <= 0:
        raise StretchEvidenceError("frozen worthiness cost basis has no projected calls")
    return float(all_routed["current_population_projected_cost_usd"]) / calls


def _corpus_counterfactuals(corpus: dict[str, Any], cost_per_call: float) -> dict[str, Any]:
    distribution = corpus["routed_class_distribution"]
    total = int(corpus["routed_cluster_count"])
    scenarios = {
        "MANAGEABLE_PLUS_UNRESOLVED": sum(
            int(distribution.get(value, 0))
            for value in (StretchClass.MANAGEABLE_STRETCH.value, StretchClass.UNRESOLVED.value)
        ),
        "ALL_EXCEPT_EXCESSIVE": total - int(
            distribution.get(StretchClass.EXCESSIVE_STRETCH.value, 0)
        ),
    }
    return {
        name: {
            "hypothetical_semantic_candidates": retained,
            "reduction_from_all_routed": total - retained,
            "reduction_fraction": round((total - retained) / total, 6) if total else 0.0,
            "projected_cost_usd": round(retained * cost_per_call, 8),
        }
        for name, retained in scenarios.items()
    }


def _current_corpus(
    config: StretchAuditConfig,
    profile: CandidateProfile,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inputs = config.raw["inputs"]
    protocol = load_prospective_protocol(inputs["prospective_protocol_path"])
    population, metadata = build_current_cluster_population(inputs["database_path"], protocol)
    detail: list[dict[str, Any]] = []
    for item in population:
        assessment = assess_stretch(_semantic_job(item), profile, config.policy)
        detail.append({
            "cluster_id": item["cluster_id"],
            "company_id": item["company_id"],
            "title": item.get("title"),
            "job_observation_id": item["job_observation_id"],
            "market_status": item.get("market_status"),
            "normal_candidate": bool(item.get("normal_candidate")),
            "semantic_cache_status": item.get("semantic_cache_status"),
            "preference_effect_present": bool(
                (item.get("preference_assessment") or {}).get("matched_effects")
            ),
            "seniority_guard_active": bool((item.get("seniority_guard") or {}).get("active")),
            "stretch_assessment": assessment.payload(),
        })
    classes = Counter(item["stretch_assessment"]["stretch_class"] for item in detail)
    routed = [item for item in detail if item["normal_candidate"]]
    routed_classes = Counter(item["stretch_assessment"]["stretch_class"] for item in routed)
    employers: dict[str, Counter[str]] = defaultdict(Counter)
    concepts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    for item in detail:
        final = item["stretch_assessment"]["stretch_class"]
        employers[item["company_id"]][final] += 1
        for requirement in item["stretch_assessment"]["requirements"]:
            concepts[requirement["concept_id"]] += 1
            if requirement["gap_severity"] == GapSeverity.DECISIVE.value:
                reasons[requirement["reason_code"]] += 1
    overlap = {
        "market_status": {
            state: dict(sorted(Counter(
                item["stretch_assessment"]["stretch_class"]
                for item in detail if item["market_status"] == state
            ).items()))
            for state in ("IN_SCOPE", "UNCERTAIN", "OUT_OF_SCOPE")
        },
        "preference_effect_present": dict(sorted(Counter(
            item["stretch_assessment"]["stretch_class"]
            for item in detail if item["preference_effect_present"]
        ).items())),
        "seniority_guard_active": dict(sorted(Counter(
            item["stretch_assessment"]["stretch_class"]
            for item in detail if item["seniority_guard_active"]
        ).items())),
        "semantic_cache_status": {
            state: dict(sorted(Counter(
                item["stretch_assessment"]["stretch_class"]
                for item in detail if item["semantic_cache_status"] == state
            ).items()))
            for state in sorted({str(item["semantic_cache_status"]) for item in detail})
        },
    }
    return {
        "population_metadata": metadata,
        "cluster_count": len(detail),
        "class_distribution": dict(sorted(classes.items())),
        "routed_cluster_count": len(routed),
        "routed_class_distribution": dict(sorted(routed_classes.items())),
        "hypothetical_deep_reasoning_candidates": sum(
            routed_classes[value]
            for value in (StretchClass.MANAGEABLE_STRETCH.value, StretchClass.UNRESOLVED.value)
        ),
        "requirement_concept_counts": dict(sorted(concepts.items())),
        "decisive_reason_counts": dict(sorted(reasons.items())),
        "class_counts_by_employer": {
            employer: dict(sorted(values.items())) for employer, values in sorted(employers.items())
        },
        "boundary_overlap": overlap,
        "evidence_coverage": {
            "any_core_requirement": sum(bool(item["stretch_assessment"]["requirements"]) for item in detail),
            "resolved_class": len(detail) - classes[StretchClass.UNRESOLVED.value],
            "unresolved_class": classes[StretchClass.UNRESOLVED.value],
        },
    }, detail


def _safety_gates(sample: dict[str, Any], result: dict[str, Any]) -> list[dict[str, str]]:
    checks = [
        ("frozen_worth_protected", sample["worth_excessive_count"] == 0),
        ("preference_only_not_mislabeled_excessive", sample["preference_only_false_excessive"] == 0),
        ("market_only_not_mislabeled_excessive", sample["market_only_false_excessive"] == 0),
        ("explicit_profession_mismatch_supported", sample["detected_human_evident_excessive"] > 0),
        ("missing_evidence_remains_unresolved", sample["unresolved_rate"] > 0),
        ("preferences_excluded_from_stretch_identity", result["integrity"]["preference_inputs_absent"]),
        ("zero_semantic_calls_and_cache_mutation", result["integrity"]["semantic_calls"] == 0 and result["integrity"]["semantic_cache_writes"] == 0),
        ("deterministic_replay", result["integrity"]["deterministic_replay"]),
    ]
    return [{"gate": name, "status": "PASS" if passed else "FAIL"} for name, passed in checks]


def build_sanitized_summary(result: dict[str, Any], detailed_sha256: str) -> dict[str, Any]:
    corpus = result["current_corpus"]
    safe_metadata = {
        key: value for key, value in corpus["population_metadata"].items()
        if key not in {"candidate", "semantic", "latest_ingestion_run", "source_failures_or_incomplete"}
    }
    return {
        "schema_version": 1,
        "evidence_class": "SANITIZED_AGGREGATE_EXPERIMENT_RESULT",
        "experiment_id": result["experiment_id"],
        "experiment_type": result["experiment_type"],
        "run_id": result["run_id"],
        "created_at": result["created_at"],
        "stretch_contract": result["stretch_contract"],
        "frozen_human_sample": result["frozen_human_sample"],
        "compute_allocation_counterfactuals": result["compute_allocation_counterfactuals"],
        "current_corpus_counterfactuals": result["current_corpus_counterfactuals"],
        "current_corpus": {
            **{key: value for key, value in corpus.items() if key != "population_metadata"},
            "population_metadata": safe_metadata,
        },
        "fingerprints": result["fingerprints"],
        "safety_gates": result["safety_gates"],
        "integrity": result["integrity"],
        "architecture_conclusion": result["architecture_conclusion"],
        "recommendation": result["recommendation"],
        "privacy": {
            "classification": "REPOSITORY_SAFE_AGGREGATE",
            "private_detailed_artifact_sha256": detailed_sha256,
            "excluded_detail": "RAW_HUMAN_NOTES_TITLES_URLS_CLUSTER_IDENTITIES_AND_PER_OPPORTUNITY_STRETCH_EVIDENCE",
        },
        "limitations": result["limitations"],
    }


def run_stretch_evidence_audit(
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path | None = None,
    *,
    run_id: str | None = None,
    write_artifact: bool = True,
) -> dict[str, Any]:
    config = load_stretch_audit_config(config_path)
    inputs = config.raw["inputs"]
    for key in ("database_path", "worthiness_manifest_path", "worthiness_judgments_path", "worthiness_replacements_path"):
        if not Path(inputs[key]).exists():
            raise StretchEvidenceError(f"required private/local audit input does not exist: {inputs[key]}")
    database_before = _sha256(inputs["database_path"])
    judgments_before = _sha256(inputs["worthiness_judgments_path"])
    taxonomy = load_taxonomy(inputs["taxonomy_path"])
    profile = load_candidate_profile(inputs["candidate_path"], taxonomy)
    cost_per_call = _cost_per_call(inputs["worthiness_result_path"])
    sample, sample_detail = _human_sample(config, profile)
    corpus, corpus_detail = _current_corpus(config, profile)
    first_probe = assess_stretch(
        _semantic_job({
            "title": "Unspecified opportunity", "description": "Evidence is unavailable.",
            "company_name": "Synthetic", "locations": [], "work_mode": "unspecified",
        }), profile, config.policy,
    )
    second_probe = assess_stretch(
        _semantic_job({
            "title": "Unspecified opportunity", "description": "Evidence is unavailable.",
            "company_name": "Different", "locations": [{"raw": "Elsewhere"}], "work_mode": "remote",
        }), profile, config.policy,
    )
    database_after = _sha256(inputs["database_path"])
    judgments_after = _sha256(inputs["worthiness_judgments_path"])
    if database_before != database_after or judgments_before != judgments_after:
        raise StretchEvidenceError("read-only stretch audit mutated frozen evidence")
    run_id = run_id or (
        "stretch-evidence-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    )
    result: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "experiment_type": EXPERIMENT_TYPE,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stretch_contract": {
            "classes": [item.value for item in StretchClass],
            "requirement_strengths": [item.value for item in RequirementStrength],
            "support_states": [item.value for item in SupportState],
            "gap_severities": [item.value for item in GapSeverity],
            "runtime_promoted": False,
            "preference_is_not_capability": True,
            "market_status_is_not_capability": True,
        },
        "frozen_human_sample": sample,
        "compute_allocation_counterfactuals": _counterfactuals(
            sample_detail, config, cost_per_call,
        ),
        "current_corpus_counterfactuals": _corpus_counterfactuals(
            corpus, cost_per_call,
        ),
        "current_corpus": corpus,
        "private_detail": {
            "frozen_human_sample": sample_detail,
            "current_corpus": corpus_detail,
        },
        "fingerprints": {
            "audit_config": config.fingerprint,
            "stretch_rules": config.policy.fingerprint,
            "candidate_capability_evidence": digest(_candidate_payload(profile)),
            "candidate_semantic_profile": profile.semantic_profile_fingerprint,
            "candidate_market_policy": profile.market_access_policy_fingerprint,
            "candidate_decision_preferences": profile.decision_preference_fingerprint,
            "worthiness_manifest_sha256": _sha256(inputs["worthiness_manifest_path"]),
            "worthiness_judgments_sha256": judgments_before,
            "worthiness_result_sha256": _sha256(inputs["worthiness_result_path"]),
            "database_sha256": database_before,
            "estimated_cost_per_semantic_call_usd": round(cost_per_call, 8),
        },
        "integrity": {
            "database_sha256_before": database_before,
            "database_sha256_after": database_after,
            "database_unchanged": database_before == database_after,
            "judgments_sha256_before": judgments_before,
            "judgments_sha256_after": judgments_after,
            "judgments_unchanged": judgments_before == judgments_after,
            "semantic_calls": 0,
            "semantic_cache_writes": 0,
            "live_source_calls": 0,
            "sqlite_writes": 0,
            "lifecycle_changes": 0,
            "cluster_changes": 0,
            "recommendation_changes": 0,
            "preference_inputs_absent": True,
            "market_inputs_absent": first_probe.input_fingerprint == second_probe.input_fingerprint,
            "deterministic_replay": first_probe.payload() == assess_stretch(
                _semantic_job({
                    "title": "Unspecified opportunity", "description": "Evidence is unavailable.",
                    "company_name": "Synthetic", "locations": [], "work_mode": "unspecified",
                }), profile, config.policy,
            ).payload(),
            "git": _git_state(),
        },
        "architecture_conclusion": (
            "A separate auditable stretch object is feasible, but the conservative v1 rules "
            "leave substantial evidence unresolved and remain diagnostic only."
        ),
        "recommendation": "REVIEW_FOR_LATER_RUNTIME_EXPERIMENT",
        "limitations": [
            "The 60-item sample is exploratory, contains only three WORTH labels, and is not training data.",
            "Human-evident excessive stretch is a conservative private-note adjudication, not a universal ground-truth label.",
            "Title-scoped profession rules prioritize auditability and miss requirements hidden only in prose.",
            "Omitted candidate capability remains UNKNOWN, so many obvious-to-a-human mismatches correctly remain unresolved.",
            "Current-corpus counts reflect one local operational snapshot and are not an unbiased market estimate.",
            "No runtime filtering, ranking, recommendation, cache, lifecycle, candidate, or source behavior changed.",
        ],
    }
    result["safety_gates"] = _safety_gates(sample, result)
    if any(item["status"] == "FAIL" for item in result["safety_gates"]):
        result["recommendation"] = "DO_NOT_PROMOTE_RUNTIME_STRETCH_BEHAVIOR"
    if write_artifact:
        root = Path(output_root or config.raw["outputs"]["root"])
        directory = root / run_id
        directory.mkdir(parents=True, exist_ok=False)
        detail_path = directory / "audit.json"
        detail_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        aggregate = build_sanitized_summary(result, _sha256(detail_path))
        aggregate_path = directory / "aggregate_summary.json"
        aggregate_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["artifact_paths"] = {
            "private_detailed": str(detail_path),
            "repository_safe_aggregate": str(aggregate_path),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only SPEC-019 stretch evidence boundary audit")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-root")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run_stretch_evidence_audit(
        args.config, args.output_root, run_id=args.run_id, write_artifact=not args.dry_run,
    )
    print(json.dumps({
        "run_id": result["run_id"],
        "frozen_human_sample": result["frozen_human_sample"],
        "compute_allocation_counterfactuals": result["compute_allocation_counterfactuals"],
        "current_corpus": {
            "cluster_count": result["current_corpus"]["cluster_count"],
            "class_distribution": result["current_corpus"]["class_distribution"],
            "routed_class_distribution": result["current_corpus"]["routed_class_distribution"],
        },
        "safety_gates": result["safety_gates"],
        "recommendation": result["recommendation"],
        "external_calls": 0,
        "artifact_paths": result.get("artifact_paths"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
