from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.phase3_config import CandidateProfile, digest, load_candidate_profile, load_taxonomy
from opportunity_radar.prospective_validation import build_current_cluster_population, load_prospective_protocol
from opportunity_radar.semantic_worthiness_validation import _current_append_only, load_jsonl
from opportunity_radar.stretch_evidence import (
    GapSeverity,
    StretchClass,
    _semantic_job,
    assess_stretch,
    load_stretch_audit_config,
)


DEFAULT_CONFIG = Path("experiments/credential_semantics_validation_v1.yaml")
DEFAULT_DATABASE = Path("output/opportunity_radar.sqlite3")
EXPERIMENT_TYPE = "CREDENTIAL_SEMANTICS_HUMAN_VALIDATION"


class CredentialValidationError(ValueError):
    pass


class EmployerCapDecisionRequired(CredentialValidationError):
    def __init__(self, diagnostic: dict[str, Any]):
        self.diagnostic = diagnostic
        super().__init__(
            "human decision required: target sample cannot satisfy employer cap "
            f"{diagnostic['requested_cap']}; minimum feasible cap is "
            f"{diagnostic['minimum_feasible_cap']}"
        )


@dataclass(frozen=True)
class CredentialProtocol:
    raw: dict[str, Any]
    fingerprint: str
    role_families: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]
    wording_patterns: dict[str, re.Pattern[str]]

    @property
    def experiment_id(self) -> str:
        return str(self.raw["experiment_id"])

    @property
    def version(self) -> str:
        return str(self.raw["protocol_version"])


def _sha256_file(path: str | Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _stable_key(seed: str, *parts: str) -> str:
    return hashlib.sha256(":".join((seed, *parts)).encode()).hexdigest()


def _unique_strings(value: Any, field: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise CredentialValidationError(f"{field} must contain unique strings")
    return value


def _compile(value: str, field: str) -> re.Pattern[str]:
    if not isinstance(value, str) or not value:
        raise CredentialValidationError(f"{field} must be a non-empty regex")
    try:
        return re.compile(value, re.I)
    except re.error as exc:
        raise CredentialValidationError(f"invalid {field}: {exc}") from exc


def load_credential_protocol(path: str | Path = DEFAULT_CONFIG) -> CredentialProtocol:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version", "protocol_version", "experiment_id", "experiment_type",
        "specification", "inputs", "source_population", "sampling", "role_families",
        "wording_patterns", "qualification_excerpt", "candidate_evidence", "human_labels",
        "replacement", "reporting", "privacy", "outputs",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise CredentialValidationError("credential protocol has an invalid top-level schema")
    if raw["schema_version"] != 1 or raw["experiment_type"] != EXPERIMENT_TYPE:
        raise CredentialValidationError("unsupported credential protocol identity")
    if not isinstance(raw["protocol_version"], str) or not raw["protocol_version"]:
        raise CredentialValidationError("protocol_version is required")
    inputs = raw["inputs"]
    if set(inputs) != {
        "stretch_config_path", "candidate_path", "taxonomy_path",
        "prospective_protocol_path", "database_path",
    }:
        raise CredentialValidationError("credential protocol inputs have an invalid schema")
    for key in ("stretch_config_path", "candidate_path", "taxonomy_path", "prospective_protocol_path"):
        if not Path(inputs[key]).exists():
            raise CredentialValidationError(f"configured input does not exist: {inputs[key]}")
    source = raw["source_population"]
    if source != {
        "stretch_class": "EXCESSIVE_STRETCH",
        "credential_concept_id": "bachelors_degree",
        "decisive_reason_code": "MANDATORY_CREDENTIAL_ABSENT",
    }:
        raise CredentialValidationError("source population must preserve SPEC-019 degree semantics")
    sampling = raw["sampling"]
    if set(sampling) != {
        "seed", "target", "employer_cap_target", "authorized_employer_cap",
        "authorized_employer_distribution", "reserve_per_major_stratum",
        "major_stratum", "cap_relaxation_status", "employer_concentration_limitation",
    }:
        raise CredentialValidationError("sampling has an invalid schema")
    for field in ("target", "employer_cap_target", "authorized_employer_cap", "reserve_per_major_stratum"):
        if not isinstance(sampling[field], int) or isinstance(sampling[field], bool) or sampling[field] <= 0:
            raise CredentialValidationError(f"sampling.{field} must be a positive integer")
    if sampling["major_stratum"] != "credential_sampling_stratum":
        raise CredentialValidationError("unsupported major sampling stratum")
    if sampling["cap_relaxation_status"] != "HUMAN_AUTHORIZED":
        raise CredentialValidationError("material employer-cap relaxation is not authorized")
    distribution = sampling["authorized_employer_distribution"]
    if (
        not isinstance(distribution, dict)
        or any(not isinstance(value, int) or value <= 0 for value in distribution.values())
        or sum(distribution.values()) != sampling["target"]
    ):
        raise CredentialValidationError("authorized employer distribution is invalid")
    if not isinstance(sampling["employer_concentration_limitation"], str) or not sampling["employer_concentration_limitation"]:
        raise CredentialValidationError("employer concentration limitation is required")
    reporting = raw["reporting"]
    if reporting != {
        "views": ["UNWEIGHTED_STRATIFIED_SAMPLE", "EMPLOYER_POPULATION_WEIGHTED_ESTIMATE"],
        "population_weight_basis": "VERIFIED_144_CASE_EMPLOYER_DISTRIBUTION",
        "complete_employer_coverage": {"schneider_electric": 6},
    }:
        raise CredentialValidationError("reporting views must preserve the approved weighting policy")
    role_families: list[tuple[str, tuple[re.Pattern[str], ...]]] = []
    seen_families: set[str] = set()
    for item in raw["role_families"]:
        if not isinstance(item, dict) or set(item) != {"family_id", "title_patterns"}:
            raise CredentialValidationError("role family has an invalid schema")
        family = str(item["family_id"])
        if not family or family in seen_families:
            raise CredentialValidationError("role family ids must be unique")
        seen_families.add(family)
        role_families.append((family, tuple(
            _compile(pattern, f"role family {family}")
            for pattern in _unique_strings(item["title_patterns"], f"role family {family}")
        )))
    wording = {
        key: _compile(value, f"wording pattern {key}")
        for key, value in raw["wording_patterns"].items()
    }
    if set(wording) != {
        "explicit_equivalent_experience", "preferred_context", "must_have", "explicitly_required",
    }:
        raise CredentialValidationError("wording patterns have an invalid schema")
    labels = raw["human_labels"]
    if not isinstance(labels, dict) or set(labels) != {
        "credential_semantics", "candidacy_consequence", "optional_reasons",
    }:
        raise CredentialValidationError("human labels have an invalid schema")
    if set(_unique_strings(labels["credential_semantics"], "credential labels")) != {
        "HARD_CREDENTIAL", "DEGREE_OR_EQUIVALENT_EXPERIENCE", "PREFERRED_CREDENTIAL",
        "GENERIC_OR_NONDECISIVE_CREDENTIAL", "AMBIGUOUS_CREDENTIAL", "INVALID_OR_STALE_EVIDENCE",
    }:
        raise CredentialValidationError("credential label vocabulary is not frozen")
    if set(_unique_strings(labels["candidacy_consequence"], "consequence labels")) != {
        "DEGREE_GAP_DECISIVE", "EXPERIENCE_PLAUSIBLY_SUBSTITUTES",
        "DEGREE_GAP_NOT_DECISIVE", "NEED_MORE_INFORMATION",
    }:
        raise CredentialValidationError("consequence label vocabulary is not frozen")
    _unique_strings(labels["optional_reasons"], "optional reasons")
    replacement = raw["replacement"]
    if set(replacement) != {"controlled_reasons"}:
        raise CredentialValidationError("replacement schema is invalid")
    _unique_strings(replacement["controlled_reasons"], "replacement reasons")
    if raw["privacy"] != {
        "manifest": "PRIVATE_LOCAL", "blind_review": "PRIVATE_LOCAL",
        "human_judgments": "PRIVATE_LOCAL_APPEND_ONLY",
        "replacements": "PRIVATE_LOCAL_APPEND_ONLY", "detailed_report": "PRIVATE_LOCAL",
        "aggregate_summary": "REPOSITORY_SAFE",
    }:
        raise CredentialValidationError("credential privacy boundary is invalid")
    if set(raw["outputs"]) != {"root", "judgments", "replacements"}:
        raise CredentialValidationError("credential output paths are invalid")
    excerpt = raw["qualification_excerpt"]
    if set(excerpt) != {"context_characters_before", "context_characters_after", "maximum_characters"}:
        raise CredentialValidationError("qualification excerpt schema is invalid")
    if excerpt["maximum_characters"] < excerpt["context_characters_before"] + excerpt["context_characters_after"]:
        raise CredentialValidationError("qualification excerpt maximum is too small")
    return CredentialProtocol(raw, digest(raw), tuple(role_families), wording)


def _role_family(title: str | None, protocol: CredentialProtocol) -> str:
    title = title or ""
    for family, patterns in protocol.role_families:
        if any(pattern.search(title) for pattern in patterns):
            return family
    return "OTHER_UNCLASSIFIED"


def _credential_match(description: str, policy: Any) -> re.Match[str] | None:
    return next(
        (pattern.search(description) for pattern in policy.mandatory_degree_patterns if pattern.search(description)),
        None,
    )


def _exact_qualification_excerpt(description: str, match: re.Match[str], protocol: CredentialProtocol) -> str:
    config = protocol.raw["qualification_excerpt"]
    left = max(0, match.start() - int(config["context_characters_before"]))
    right = min(len(description), match.end() + int(config["context_characters_after"]))
    # Prefer real text boundaries without rewriting or whitespace normalization.
    prior = max(description.rfind("\n", left, match.start()), description.rfind(". ", left, match.start()))
    if prior >= left:
        left = prior + (2 if description[prior: prior + 2] == ". " else 1)
    following = [value for value in (
        description.find("\n", match.end(), right), description.find(". ", match.end(), right),
    ) if value >= 0]
    if following:
        right = min(following) + (1 if description[min(following)] == "." else 0)
    excerpt = description[left:right].strip()
    maximum = int(config["maximum_characters"])
    if len(excerpt) > maximum:
        excerpt = description[max(0, match.start() - maximum // 3):match.start() + 2 * maximum // 3].strip()
    if match.group(0) not in excerpt:
        raise CredentialValidationError("bounded excerpt lost exact credential wording")
    return excerpt


def _wording_pattern(excerpt: str, match: re.Match[str], protocol: CredentialProtocol) -> str:
    if protocol.wording_patterns["explicit_equivalent_experience"].search(excerpt):
        return "EXPLICIT_EQUIVALENT_EXPERIENCE"
    if protocol.wording_patterns["preferred_context"].search(excerpt):
        return "MIXED_PREFERRED_CONTEXT"
    if protocol.wording_patterns["must_have"].search(match.group(0)):
        return "MUST_HAVE"
    if protocol.wording_patterns["explicitly_required"].search(match.group(0)):
        return "EXPLICITLY_REQUIRED"
    return "MANDATORY_TEMPLATE_WORDING"


def _sampling_stratum(wording_pattern: str) -> str:
    if wording_pattern in {"EXPLICIT_EQUIVALENT_EXPERIENCE", "MIXED_PREFERRED_CONTEXT"}:
        return "QUALIFIED_OR_SUBSTITUTABLE_WORDING"
    return "DIRECT_MANDATORY_WORDING"


def _candidate_summary(profile: CandidateProfile, assessment: Any, protocol: CredentialProtocol) -> dict[str, Any]:
    relevant_ids = {
        capability_id
        for requirement in assessment.requirements
        for capability_id in re.findall(r"capabilities\[([^]]+)\]", " ".join(requirement.candidate_evidence))
    }
    capabilities = [
        {"capability_id": item["capability_id"], "level": item["level"], "confidence": item["confidence"]}
        for item in profile.capabilities if item["capability_id"] in relevant_ids
    ][: int(protocol.raw["candidate_evidence"]["maximum_relevant_capabilities"])]
    return {
        "total_technology_business_years": profile.facts.get("career", {}).get("technology_years"),
        "completed_bachelors_degree": profile.facts.get("education", {}).get("completed_bachelors_degree"),
        "leadership": {
            "people_management": profile.facts.get("leadership", {}).get("people_management"),
            "senior_stakeholder_exposure": profile.facts.get("leadership", {}).get("senior_stakeholder_exposure"),
        },
        "role_history_summary": list(profile.experience.get("role_history_summary", []))[
            : int(protocol.raw["candidate_evidence"]["maximum_role_history_items"])
        ],
        "relevant_asserted_capabilities": capabilities,
    }


def build_credential_population(
    protocol: CredentialProtocol,
    database: str | Path = DEFAULT_DATABASE,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    stretch = load_stretch_audit_config(protocol.raw["inputs"]["stretch_config_path"])
    taxonomy = load_taxonomy(protocol.raw["inputs"]["taxonomy_path"])
    profile = load_candidate_profile(protocol.raw["inputs"]["candidate_path"], taxonomy)
    prospective = load_prospective_protocol(protocol.raw["inputs"]["prospective_protocol_path"])
    population, metadata = build_current_cluster_population(database, prospective)
    rows: list[dict[str, Any]] = []
    source = protocol.raw["source_population"]
    for row in population:
        assessment = assess_stretch(_semantic_job(row), profile, stretch.policy)
        if assessment.stretch_class.value != source["stretch_class"]:
            continue
        credential = next((
            item for item in assessment.requirements
            if item.concept_id == source["credential_concept_id"]
            and item.gap_severity is GapSeverity.DECISIVE
            and item.reason_code == source["decisive_reason_code"]
        ), None)
        if credential is None:
            continue
        description = str(row.get("description") or "")
        match = _credential_match(description, stretch.policy)
        if match is None:
            raise CredentialValidationError("SPEC-019 decisive credential evidence is not reproducible")
        excerpt = _exact_qualification_excerpt(description, match, protocol)
        other_decisive = sorted(
            item.concept_id for item in assessment.requirements
            if item.gap_severity is GapSeverity.DECISIVE and item.concept_id != "bachelors_degree"
        )
        years = [int(value) for value in stretch.policy.required_years_pattern.findall(excerpt)]
        wording_pattern = _wording_pattern(excerpt, match, protocol)
        rows.append({
            "cluster_id": str(row["cluster_id"]),
            "cluster_fingerprint": str(row["cluster_fingerprint"]),
            "company_id": str(row["company_id"]),
            "company_name": row.get("company_name"),
            "job_observation_id": row.get("job_observation_id"),
            "title": row.get("title"),
            "locations": row.get("locations", []),
            "work_mode": row.get("work_mode"),
            "canonical_url": row.get("canonical_url"),
            "credential_match": match.group(0),
            "qualification_excerpt": excerpt,
            "qualification_excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
            "credential_wording_pattern": wording_pattern,
            "credential_sampling_stratum": _sampling_stratum(wording_pattern),
            "role_family": _role_family(row.get("title"), protocol),
            "explicit_years_minimum": max(years) if years else None,
            "elevated_title_context": any(pattern.search(row.get("title") or "") for pattern in stretch.policy.elevated_title_patterns),
            "degree_evidence_only_decisive": not other_decisive,
            "other_decisive_concepts": other_decisive,
            "candidate_evidence": _candidate_summary(profile, assessment, protocol),
        })
    rows.sort(key=lambda item: item["cluster_id"])
    meta = {
        "active_cluster_count": len(population),
        "source_population_count": len(rows),
        "company_distribution": dict(sorted(Counter(item["company_id"] for item in rows).items())),
        "role_family_distribution": dict(sorted(Counter(item["role_family"] for item in rows).items())),
        "wording_pattern_distribution": dict(sorted(Counter(item["credential_wording_pattern"] for item in rows).items())),
        "years_context_count": sum(item["explicit_years_minimum"] is not None for item in rows),
        "degree_only_decisive_count": sum(item["degree_evidence_only_decisive"] for item in rows),
        "population_fingerprint": digest([
            (item["cluster_id"], item["cluster_fingerprint"], item["qualification_excerpt_sha256"])
            for item in rows
        ]),
        "upstream_population_metadata": metadata,
        "stretch_rules_fingerprint": stretch.policy.fingerprint,
        "candidate_full_profile_fingerprint": profile.full_profile_fingerprint,
        "candidate_semantic_profile_fingerprint": profile.semantic_profile_fingerprint,
    }
    return rows, meta


def _minimum_cap(company_counts: Counter[str], target: int) -> int | None:
    if sum(company_counts.values()) < target:
        return None
    for cap in range(1, target + 1):
        if sum(min(count, cap) for count in company_counts.values()) >= target:
            return cap
    return None


def cap_diagnostic(population: list[dict[str, Any]], protocol: CredentialProtocol) -> dict[str, Any]:
    counts = Counter(item["company_id"] for item in population)
    target = int(protocol.raw["sampling"]["target"])
    requested = int(protocol.raw["sampling"]["employer_cap_target"])
    minimum = _minimum_cap(counts, target)
    return {
        "population_count": len(population),
        "employer_count": len(counts),
        "target": target,
        "requested_cap": requested,
        "maximum_sample_at_requested_cap": sum(min(count, requested) for count in counts.values()),
        "minimum_feasible_cap": minimum,
        "authorized_cap": protocol.raw["sampling"]["authorized_employer_cap"],
        "authorized_distribution": protocol.raw["sampling"]["authorized_employer_distribution"],
        "material_relaxation_required": minimum is not None and minimum > requested,
        "minimum_cap_distribution": {
            company: min(count, minimum or 0) for company, count in sorted(counts.items())
        },
    }


def select_credential_sample(
    population: list[dict[str, Any]],
    protocol: CredentialProtocol,
) -> dict[str, Any]:
    allowed = {
        "cluster_id", "cluster_fingerprint", "company_id", "company_name",
        "job_observation_id", "title", "locations", "work_mode", "canonical_url",
        "credential_match", "qualification_excerpt", "qualification_excerpt_sha256",
        "credential_wording_pattern", "credential_sampling_stratum", "role_family", "explicit_years_minimum",
        "elevated_title_context", "degree_evidence_only_decisive",
        "other_decisive_concepts", "candidate_evidence",
    }
    population = [{key: value for key, value in item.items() if key in allowed} for item in population]
    diagnostic = cap_diagnostic(population, protocol)
    if diagnostic["minimum_feasible_cap"] is None:
        raise CredentialValidationError("verified credential population cannot fill target sample")
    requested = diagnostic["requested_cap"]
    effective = int(diagnostic["minimum_feasible_cap"])
    authorized = int(protocol.raw["sampling"]["authorized_employer_cap"])
    if effective > requested and authorized != effective:
        raise EmployerCapDecisionRequired(diagnostic)
    seed = str(protocol.raw["sampling"]["seed"])
    cap = authorized
    ordered = sorted(population, key=lambda item: _stable_key(
        seed, item["credential_wording_pattern"], item["role_family"], item["company_id"], item["cluster_id"],
    ))
    chosen: list[dict[str, Any]] = []
    company_counts: Counter[str] = Counter()
    wording_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    remaining = list(ordered)
    while len(chosen) < diagnostic["target"]:
        candidates = [item for item in remaining if company_counts[item["company_id"]] < cap]
        if not candidates:
            raise CredentialValidationError("balanced sampler could not fill target")
        candidates.sort(key=lambda item: (
            company_counts[item["company_id"]], wording_counts[item["credential_wording_pattern"]],
            role_counts[item["role_family"]], _stable_key(seed, "take", item["cluster_id"]),
        ))
        item = candidates[0]
        chosen.append(item)
        remaining.remove(item)
        company_counts[item["company_id"]] += 1
        wording_counts[item["credential_wording_pattern"]] += 1
        role_counts[item["role_family"]] += 1
    chosen_ids = {item["cluster_id"] for item in chosen}
    reserve_target = int(protocol.raw["sampling"]["reserve_per_major_stratum"])
    strata = sorted({item["credential_sampling_stratum"] for item in chosen})
    reserves: dict[str, list[dict[str, Any]]] = {}
    for stratum in strata:
        values = [
            item for item in population
            if item["cluster_id"] not in chosen_ids and item["credential_sampling_stratum"] == stratum
        ]
        values.sort(key=lambda item: _stable_key(seed, "reserve", stratum, item["company_id"], item["cluster_id"]))
        reserves[stratum] = values[:reserve_target]
    insufficient = {key: len(value) for key, value in reserves.items() if len(value) < reserve_target}
    if insufficient:
        raise CredentialValidationError(f"major strata lack five frozen reserves: {insufficient}")
    chosen.sort(key=lambda item: _stable_key(seed, "review", item["cluster_id"]))
    selected = [dict(item, review_number=index) for index, item in enumerate(chosen, 1)]
    authorized_distribution = protocol.raw["sampling"]["authorized_employer_distribution"]
    population_companies = {item["company_id"] for item in population}
    if (
        population_companies == set(authorized_distribution)
        and dict(sorted(company_counts.items())) != dict(sorted(authorized_distribution.items()))
    ):
        raise CredentialValidationError("deterministic selection does not match authorized employer distribution")
    return {
        "selected": selected,
        "reserves": {
            key: [dict(item, reserve_order=index) for index, item in enumerate(values, 1)]
            for key, values in reserves.items()
        },
        "employer_cap_diagnostic": diagnostic,
        "employer_cap_effective": cap,
        "employer_distribution": dict(sorted(company_counts.items())),
        "wording_pattern_distribution": dict(sorted(wording_counts.items())),
        "role_family_distribution": dict(sorted(role_counts.items())),
        "selection_fingerprint": digest([
            (item["review_number"], item["cluster_id"], item["credential_sampling_stratum"])
            for item in selected
        ]),
    }


def _location_text(item: dict[str, Any]) -> str:
    values = []
    for location in item.get("locations", []):
        value = location.get("raw") or ", ".join(
            str(location.get(key)) for key in ("city", "region", "country") if location.get(key)
        )
        if value:
            values.append(value)
    return "; ".join(values) or "Not stated"


def render_blind_review(manifest: dict[str, Any], items: list[dict[str, Any]] | None = None) -> str:
    items = items or manifest["sample"]["selected"]
    lines = [
        f"# Credential Semantics Review — {manifest['preparation_id']}", "",
        "> Private human-review evidence. Do not commit this file.", "",
        "Answer both questions independently. This is not an APPLY/DONT_APPLY review.", "",
        "Question A labels: `HARD_CREDENTIAL`, `DEGREE_OR_EQUIVALENT_EXPERIENCE`, "
        "`PREFERRED_CREDENTIAL`, `GENERIC_OR_NONDECISIVE_CREDENTIAL`, "
        "`AMBIGUOUS_CREDENTIAL`, `INVALID_OR_STALE_EVIDENCE`.", "",
        "Question B labels: `DEGREE_GAP_DECISIVE`, `EXPERIENCE_PLAUSIBLY_SUBSTITUTES`, "
        "`DEGREE_GAP_NOT_DECISIVE`, `NEED_MORE_INFORMATION`.", "",
    ]
    for item in sorted(items, key=lambda value: int(value["review_number"])):
        candidate = item["candidate_evidence"]
        lines.extend([
            f"## Review {item['review_number']}", "",
            f"Employer: {item.get('company_name') or 'Not stated'}", "",
            f"Role: {item.get('title') or 'Not stated'}", "",
            f"Location: {_location_text(item)}", "",
            f"Work mode: {item.get('work_mode') or 'unspecified'}", "",
            "Exact credential wording:", "", item["credential_match"], "",
            "Bounded qualification excerpt:", "", item["qualification_excerpt"], "",
            "Candidate credential/substitution evidence:", "",
            f"- Technology/business experience: approximately {candidate.get('total_technology_business_years') or 'unknown'} years",
            f"- Completed bachelor's degree: {candidate.get('completed_bachelors_degree')}",
            f"- People-management history: {candidate['leadership'].get('people_management')}",
            f"- Senior-stakeholder exposure: {candidate['leadership'].get('senior_stakeholder_exposure')}",
        ])
        lines.extend(f"- Professional history: {value}" for value in candidate["role_history_summary"])
        lines.extend(
            f"- Relevant asserted capability: {value['capability_id']} / {value['level']} / {value['confidence']}"
            for value in candidate["relevant_asserted_capabilities"]
        )
        lines.extend([
            "", f"Source: {item.get('canonical_url') or 'Not available'}", "",
            "Question A: ____________________", "Question B: ____________________",
            "Controlled reason(s), optional: ____________________",
            "Private note, optional: ____________________", "",
        ])
    text = "\n".join(lines).rstrip() + "\n"
    forbidden = ("EXCESSIVE_STRETCH", "semantic_cache", "recommendation", "triage")
    if any(value.lower() in text.lower() for value in forbidden):
        raise CredentialValidationError("blind review leaked hidden evaluation evidence")
    return text


def _write_immutable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


def _git_state() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], check=True, capture_output=True, text=True).stdout
    return {"commit": commit, "dirty": bool(status), "worktree_status_fingerprint": hashlib.sha256(status.encode()).hexdigest()}


def _safe_blocker_summary(
    protocol: CredentialProtocol,
    metadata: dict[str, Any],
    diagnostic: dict[str, Any],
    database_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_type": "REPOSITORY_SAFE_CREDENTIAL_PREPARATION_BLOCKER",
        "experiment_id": protocol.experiment_id,
        "protocol_version": protocol.version,
        "status": "BLOCKED_EMPLOYER_CONCENTRATION_DECISION_REQUIRED",
        "verified_population": {
            "count": metadata["source_population_count"],
            "employer_count": diagnostic["employer_count"],
            "role_family_distribution": metadata["role_family_distribution"],
            "wording_pattern_distribution": metadata["wording_pattern_distribution"],
            "years_context_count": metadata["years_context_count"],
            "degree_only_decisive_count": metadata["degree_only_decisive_count"],
        },
        "sampling_stop": diagnostic,
        "fingerprints": {
            "protocol": protocol.fingerprint,
            "population": metadata["population_fingerprint"],
            "stretch_rules": metadata["stretch_rules_fingerprint"],
            "candidate_full_profile": metadata["candidate_full_profile_fingerprint"],
            "candidate_semantic_profile": metadata["candidate_semantic_profile_fingerprint"],
            "database_sha256": database_hash,
        },
        "provenance": {"git": _git_state()},
        "integrity": {
            "sample_frozen": False, "human_review_started": False, "human_judgments_created": 0,
            "external_semantic_calls": 0, "live_source_calls": 0, "sqlite_writes": 0,
        },
        "privacy": {
            "classification": "REPOSITORY_SAFE_AGGREGATE",
            "excluded": "VACANCY_IDENTITIES_TITLES_URLS_QUALIFICATION_EXCERPTS_CANDIDATE_EVIDENCE_AND_HUMAN_NOTES",
        },
        "required_human_decision": "Authorize effective employer cap 22 for target 50, reduce target, or redesign the source population.",
    }


def prepare_credential_validation(
    database: str | Path = DEFAULT_DATABASE,
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path | None = None,
    *,
    preparation_id: str | None = None,
) -> dict[str, Any]:
    protocol = load_credential_protocol(config_path)
    database = Path(database)
    before_hash = _sha256_file(database)
    before_mtime = database.stat().st_mtime_ns
    population, metadata = build_credential_population(protocol, database)
    try:
        selection = select_credential_sample(population, protocol)
    except EmployerCapDecisionRequired as exc:
        if _sha256_file(database) != before_hash or database.stat().st_mtime_ns != before_mtime:
            raise CredentialValidationError("preparation diagnostic mutated operational SQLite")
        return {
            "status": "BLOCKED_EMPLOYER_CONCENTRATION_DECISION_REQUIRED",
            "aggregate": _safe_blocker_summary(protocol, metadata, exc.diagnostic, before_hash),
        }
    replayed_selection = select_credential_sample(population, protocol)
    if selection != replayed_selection:
        raise CredentialValidationError("credential sample selection is not deterministic")
    preparation_id = preparation_id or (
        "credential-semantics-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    )
    directory = Path(output_root or protocol.raw["outputs"]["root"]) / preparation_id
    manifest = {
        "schema_version": 1,
        "artifact_type": "PRIVATE_CREDENTIAL_SEMANTICS_SAMPLE",
        "preparation_id": preparation_id,
        "experiment_id": protocol.experiment_id,
        "protocol_version": protocol.version,
        "protocol_fingerprint": protocol.fingerprint,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "questions": {
            "credential_semantics": "How should the stated credential requirement be interpreted?",
            "candidacy_consequence": "Would absence of a completed bachelor's degree by itself make candidacy unrealistic?",
        },
        "human_labels": protocol.raw["human_labels"],
        "replacement": protocol.raw["replacement"],
        "sample": selection,
        "population": metadata,
        "integrity": {"database_sha256": before_hash, "external_semantic_calls": 0, "live_source_calls": 0, "human_judgments_created": 0},
        "privacy": protocol.raw["privacy"],
    }
    review = render_blind_review(manifest)
    _write_immutable(directory / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _write_immutable(directory / "blind_review.md", review)
    if _sha256_file(database) != before_hash or database.stat().st_mtime_ns != before_mtime:
        raise CredentialValidationError("preparation mutated operational SQLite")
    aggregate = {
        "schema_version": 1,
        "artifact_type": "REPOSITORY_SAFE_CREDENTIAL_PREPARATION",
        "experiment_id": protocol.experiment_id,
        "preparation_id": preparation_id,
        "status": "PREPARED_AWAITING_HUMAN_REVIEW",
        "verified_population_count": metadata["source_population_count"],
        "sample": {
            "selected_count": len(selection["selected"]),
            "reserve_counts": {key: len(value) for key, value in selection["reserves"].items()},
            "employer_cap_requested": selection["employer_cap_diagnostic"]["requested_cap"],
            "employer_cap_effective": selection["employer_cap_effective"],
            "employer_count": len(selection["employer_distribution"]),
            "employer_distribution": selection["employer_distribution"],
            "employer_population_distribution": metadata["company_distribution"],
            "role_family_distribution": selection["role_family_distribution"],
            "wording_pattern_distribution": selection["wording_pattern_distribution"],
            "selection_fingerprint": selection["selection_fingerprint"],
            "review_order_fingerprint": digest([
                (item["review_number"], item["cluster_id"])
                for item in selection["selected"]
            ]),
            "sample_and_reserve_fingerprint": digest({
                "selected": [
                    (item["review_number"], item["cluster_id"], item["qualification_excerpt_sha256"])
                    for item in selection["selected"]
                ],
                "reserves": {
                    key: [(item["reserve_order"], item["cluster_id"], item["qualification_excerpt_sha256"])
                          for item in values]
                    for key, values in sorted(selection["reserves"].items())
                },
            }),
        },
        "reporting_policy": {
            **protocol.raw["reporting"],
            "employer_concentration_limitation": protocol.raw["sampling"]["employer_concentration_limitation"],
            "balanced_sample_proportions_are_population_prevalence": False,
        },
        "fingerprints": {
            "protocol": protocol.fingerprint, "population": metadata["population_fingerprint"],
            "stretch_rules": metadata["stretch_rules_fingerprint"], "database_sha256": before_hash,
            "candidate_full_profile": metadata["candidate_full_profile_fingerprint"],
            "candidate_semantic_profile": metadata["candidate_semantic_profile_fingerprint"],
            "private_manifest_sha256": _sha256_file(directory / "manifest.json"),
            "private_blind_review_sha256": _sha256_file(directory / "blind_review.md"),
        },
        "provenance": {"git": _git_state()},
        "integrity": {
            "database_unchanged": True,
            "database_sha256_before": before_hash,
            "database_sha256_after": _sha256_file(database),
            "database_mtime_unchanged": database.stat().st_mtime_ns == before_mtime,
            "deterministic_selection_replay": True,
            "exact_qualification_wording_preserved": all(
                item["credential_match"] in item["qualification_excerpt"]
                for item in selection["selected"]
            ),
            "selection_independence": {
                "semantic_cache_state_excluded": True,
                "recommendation_excluded": True,
                "decision_preferences_excluded": True,
                "hidden_stretch_payload_excluded_after_source_population_filter": True,
                "historical_human_labels_excluded": True,
            },
            "blind_review_hides_hidden_evaluation": True,
            "external_semantic_calls": 0,
            "live_source_calls": 0,
            "human_judgments_created": 0,
        },
        "privacy": {"classification": "REPOSITORY_SAFE_AGGREGATE", "vacancy_level_evidence_excluded": True},
    }
    _write_immutable(directory / "aggregate_summary.json", json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n")
    return {"status": aggregate["status"], "manifest": manifest, "aggregate": aggregate, "directory": str(directory)}


def load_preparation(root: str | Path, preparation_id: str) -> dict[str, Any]:
    path = Path(root) / preparation_id / "manifest.json"
    if not path.exists():
        raise CredentialValidationError(f"preparation not found: {preparation_id}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("preparation_id") != preparation_id:
        raise CredentialValidationError("preparation identity mismatch")
    return value


def _append_jsonl(path: str | Path, value: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def current_replacements(records: list[dict[str, Any]], preparation_id: str) -> list[dict[str, Any]]:
    return sorted(
        (item for item in records if item.get("preparation_id") == preparation_id),
        key=lambda item: item["replaced_at"],
    )


def effective_selected_items(manifest: dict[str, Any], replacements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = {int(item["review_number"]): dict(item) for item in manifest["sample"]["selected"]}
    reserves = {item["cluster_id"]: item for values in manifest["sample"]["reserves"].values() for item in values}
    for row in current_replacements(replacements, manifest["preparation_id"]):
        review = int(row["review_number"])
        current = selected.get(review)
        if current is None or current["cluster_id"] != row["replaced_cluster_id"]:
            raise CredentialValidationError("invalid replacement chain")
        replacement = reserves.get(row["replacement_cluster_id"])
        if replacement is None or replacement["credential_sampling_stratum"] != current["credential_sampling_stratum"]:
            raise CredentialValidationError("replacement must use the frozen same-stratum reserve")
        selected[review] = dict(replacement, review_number=review)
    return [selected[index] for index in sorted(selected)]


def append_replacement(
    manifest: dict[str, Any], replacements_path: str | Path, judgments_path: str | Path,
    review_number: int, reason: str,
) -> dict[str, Any]:
    if reason not in set(manifest["replacement"]["controlled_reasons"]):
        raise CredentialValidationError("invalid replacement reason")
    replacements = load_jsonl(replacements_path)
    current = {item["review_number"]: item for item in effective_selected_items(manifest, replacements)}.get(review_number)
    if current is None:
        raise CredentialValidationError("review number not found")
    judgments = _current_append_only(load_jsonl(judgments_path), manifest["preparation_id"], "cluster_id")
    if current["cluster_id"] in judgments:
        raise CredentialValidationError("cannot replace an item after judgment")
    used = {item["replacement_cluster_id"] for item in replacements if item.get("preparation_id") == manifest["preparation_id"]}
    reserves = manifest["sample"]["reserves"].get(current["credential_sampling_stratum"], [])
    replacement = next((item for item in reserves if item["cluster_id"] not in used), None)
    if replacement is None:
        raise CredentialValidationError("no frozen same-stratum reserve remains")
    value = {
        "record_id": str(uuid.uuid4()), "preparation_id": manifest["preparation_id"],
        "review_number": review_number, "major_stratum": current["credential_sampling_stratum"],
        "replaced_cluster_id": current["cluster_id"], "replacement_cluster_id": replacement["cluster_id"],
        "reason": reason, "replaced_at": datetime.now(timezone.utc).isoformat(),
    }
    _append_jsonl(replacements_path, value)
    return value


def append_judgment(
    manifest: dict[str, Any], judgments_path: str | Path, replacements_path: str | Path,
    credential_label: str, consequence_label: str, *, review_number: int,
    reasons: list[str] | None = None, note: str | None = None, supersedes: str | None = None,
) -> dict[str, Any]:
    labels = manifest["human_labels"]
    if credential_label not in labels["credential_semantics"]:
        raise CredentialValidationError("invalid credential semantics label")
    if consequence_label not in labels["candidacy_consequence"]:
        raise CredentialValidationError("invalid candidacy consequence label")
    reasons = reasons or []
    if set(reasons) - set(labels["optional_reasons"]):
        raise CredentialValidationError("invalid controlled reason")
    items = {item["review_number"]: item for item in effective_selected_items(manifest, load_jsonl(replacements_path))}
    item = items.get(review_number)
    if item is None:
        raise CredentialValidationError("review number not found")
    current = _current_append_only(load_jsonl(judgments_path), manifest["preparation_id"], "cluster_id")
    existing = current.get(item["cluster_id"])
    if existing and not supersedes:
        raise CredentialValidationError(f"current judgment exists; supersede {existing['record_id']}")
    if supersedes and (existing is None or existing["record_id"] != supersedes):
        raise CredentialValidationError("supersedes must identify the current judgment")
    value = {
        "record_id": str(uuid.uuid4()), "preparation_id": manifest["preparation_id"],
        "review_number": review_number, "cluster_id": item["cluster_id"],
        "credential_label": credential_label, "consequence_label": consequence_label,
        "reasons": reasons, "note": note, "recorded_at": datetime.now(timezone.utc).isoformat(),
        "supersedes_record_id": supersedes,
    }
    _append_jsonl(judgments_path, value)
    return value


def calculate_metrics(
    manifest: dict[str, Any], judgments: list[dict[str, Any]], replacements: list[dict[str, Any]],
) -> dict[str, Any]:
    current = _current_append_only(judgments, manifest["preparation_id"], "cluster_id")
    effective = effective_selected_items(manifest, replacements)
    pairs = [(item, current[item["cluster_id"]]) for item in effective if item["cluster_id"] in current]
    records = [record for _, record in pairs]
    if len(records) < len(effective):
        return {"status": "IN_PROGRESS", "reviewed": len(records), "target": len(effective), "remaining": len(effective) - len(records)}
    credential = Counter(item["credential_label"] for item in records)
    consequence = Counter(item["consequence_label"] for item in records)
    strict = sum(
        item["credential_label"] == "HARD_CREDENTIAL" and item["consequence_label"] == "DEGREE_GAP_DECISIVE"
        for item in records
    )
    broader = sum(
        item["consequence_label"] == "DEGREE_GAP_DECISIVE"
        or (item["credential_label"] == "HARD_CREDENTIAL" and item["consequence_label"] != "EXPERIENCE_PLAUSIBLY_SUBSTITUTES")
        for item in records
    )
    false_excessive = sum(
        item["credential_label"] in {
            "DEGREE_OR_EQUIVALENT_EXPERIENCE", "PREFERRED_CREDENTIAL", "GENERIC_OR_NONDECISIVE_CREDENTIAL",
        } or item["consequence_label"] in {"EXPERIENCE_PLAUSIBLY_SUBSTITUTES", "DEGREE_GAP_NOT_DECISIVE"}
        for item in records
    )
    total = len(records)
    def grouped(field: str) -> dict[str, Any]:
        values: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item, record in pairs:
            values[str(item.get(field) or "UNKNOWN")].append(record)
        return {
            key: {
                "reviewed": len(group),
                "hard_credential": sum(row["credential_label"] == "HARD_CREDENTIAL" for row in group),
                "degree_gap_decisive": sum(row["consequence_label"] == "DEGREE_GAP_DECISIVE" for row in group),
                "substitutable_or_nondecisive": sum(
                    row["credential_label"] in {
                        "DEGREE_OR_EQUIVALENT_EXPERIENCE", "PREFERRED_CREDENTIAL",
                        "GENERIC_OR_NONDECISIVE_CREDENTIAL",
                    } or row["consequence_label"] in {
                        "EXPERIENCE_PLAUSIBLY_SUBSTITUTES", "DEGREE_GAP_NOT_DECISIVE",
                    }
                    for row in group
                ),
            }
            for key, group in sorted(values.items())
        }

    hard_or_no_equivalent = sum(
        record["credential_label"] == "HARD_CREDENTIAL"
        or (
            item["credential_wording_pattern"] not in {"EXPLICIT_EQUIVALENT_EXPERIENCE", "MIXED_PREFERRED_CONTEXT"}
            and record["consequence_label"] == "DEGREE_GAP_DECISIVE"
        )
        for item, record in pairs
    )
    population_patterns = manifest.get("population", {}).get("wording_pattern_distribution", {})
    population_companies = manifest.get("population", {}).get("company_distribution", {})
    sampled_patterns = grouped("credential_wording_pattern")
    projected = 0.0
    for pattern, count in population_patterns.items():
        sample = sampled_patterns.get(pattern)
        if sample and sample["reviewed"]:
            projected += int(count) * sample["degree_gap_decisive"] / sample["reviewed"]

    weighted_label_counts = {label: 0.0 for label in credential}
    weighted_consequence_counts = {label: 0.0 for label in consequence}
    weighted_strict = 0.0
    weighted_false = 0.0
    for company, population_count in population_companies.items():
        company_pairs = [(item, record) for item, record in pairs if item["company_id"] == company]
        if not company_pairs:
            continue
        sample_count = len(company_pairs)
        weight = int(population_count) / sample_count
        for _, record in company_pairs:
            weighted_label_counts.setdefault(record["credential_label"], 0.0)
            weighted_label_counts[record["credential_label"]] += weight
            weighted_consequence_counts.setdefault(record["consequence_label"], 0.0)
            weighted_consequence_counts[record["consequence_label"]] += weight
            weighted_strict += weight * (
                record["credential_label"] == "HARD_CREDENTIAL"
                and record["consequence_label"] == "DEGREE_GAP_DECISIVE"
            )
            weighted_false += weight * (
                record["credential_label"] in {
                    "DEGREE_OR_EQUIVALENT_EXPERIENCE", "PREFERRED_CREDENTIAL",
                    "GENERIC_OR_NONDECISIVE_CREDENTIAL",
                } or record["consequence_label"] in {
                    "EXPERIENCE_PLAUSIBLY_SUBSTITUTES", "DEGREE_GAP_NOT_DECISIVE",
                }
            )
    weighted_total = sum(int(value) for value in population_companies.values())

    return {
        "status": "COMPLETE", "reviewed": total, "target": len(effective),
        "credential_semantics_distribution": dict(sorted(credential.items())),
        "candidacy_consequence_distribution": dict(sorted(consequence.items())),
        "current_rule_precision": {"strict_count": strict, "strict_rate": round(strict / total, 6), "broader_count": broader, "broader_rate": round(broader / total, 6)},
        "false_excessive_risk": {"count": false_excessive, "rate": round(false_excessive / total, 6)},
        "ambiguity": {
            "ambiguous_credential_count": credential["AMBIGUOUS_CREDENTIAL"],
            "ambiguous_credential_rate": round(credential["AMBIGUOUS_CREDENTIAL"] / total, 6),
            "need_more_information_count": consequence["NEED_MORE_INFORMATION"],
            "need_more_information_rate": round(consequence["NEED_MORE_INFORMATION"] / total, 6),
        },
        "bounded_group_effects": {
            "employer": grouped("company_id"),
            "role_family": grouped("role_family"),
            "wording_pattern": sampled_patterns,
        },
        "reporting_views": {
            "UNWEIGHTED_STRATIFIED_SAMPLE": {
                "denominator": total,
                "credential_semantics_distribution": dict(sorted(credential.items())),
                "candidacy_consequence_distribution": dict(sorted(consequence.items())),
                "strict_precision": round(strict / total, 6),
                "false_excessive_risk": round(false_excessive / total, 6),
                "interpretation": "Cross-employer and wording-pattern validation; not a population prevalence estimate.",
            },
            "EMPLOYER_POPULATION_WEIGHTED_ESTIMATE": {
                "denominator": weighted_total or None,
                "weight_basis": "VERIFIED_144_CASE_EMPLOYER_DISTRIBUTION",
                "credential_semantics_estimated_counts": {
                    key: round(value, 2) for key, value in sorted(weighted_label_counts.items())
                },
                "candidacy_consequence_estimated_counts": {
                    key: round(value, 2) for key, value in sorted(weighted_consequence_counts.items())
                },
                "strict_precision_estimate": round(weighted_strict / weighted_total, 6) if weighted_total else None,
                "false_excessive_risk_estimate": round(weighted_false / weighted_total, 6) if weighted_total else None,
                "schneider_electric_complete_coverage": population_companies.get("schneider_electric") == 6,
            },
        },
        "counterfactuals": {
            "CURRENT_SPEC019_RULE": {"excessive_sample_count": total},
            "HARD_ONLY": {"excessive_sample_count": credential["HARD_CREDENTIAL"]},
            "HARD_OR_NO_EQUIVALENT": {"excessive_sample_count": hard_or_no_equivalent},
            "HARD_AND_DECISIVE": {"excessive_sample_count": strict},
            "SEPARATE_CREDENTIAL_OBJECT": {"degree_driven_capability_excessive_sample_count": 0},
            "AMBIGUITY_UNRESOLVED": {"unresolved_sample_count": credential["AMBIGUOUS_CREDENTIAL"] + consequence["NEED_MORE_INFORMATION"]},
            "CURRENT_CORPUS_DIRECTIONAL_PROJECTION": {
                "basis": "SAMPLE_DEGREE_GAP_DECISIVE_RATE_BY_WORDING_PATTERN",
                "projected_excessive_count": round(projected, 2) if population_patterns else None,
                "source_population_count": sum(int(value) for value in population_patterns.values()),
            },
        },
        "frozen_worth_protection": {"status": "NOT_AVAILABLE_WITHOUT_SEPARATE_FROZEN_CROSS_EVIDENCE"},
    }


def build_safe_final_summary(manifest: dict[str, Any], metrics: dict[str, Any], judgments_path: str | Path) -> dict[str, Any]:
    if metrics["status"] != "COMPLETE":
        raise CredentialValidationError("final summary requires complete review")
    return {
        "schema_version": 1, "artifact_type": "REPOSITORY_SAFE_CREDENTIAL_RESULT",
        "experiment_id": manifest["experiment_id"], "preparation_id": manifest["preparation_id"],
        "status": "COMPLETE", "metrics": metrics,
        "fingerprints": {
            "protocol": manifest["protocol_fingerprint"],
            "selection": manifest["sample"]["selection_fingerprint"],
            "judgment_log_sha256": _sha256_file(judgments_path),
        },
        "privacy": {"classification": "REPOSITORY_SAFE_AGGREGATE", "vacancy_level_judgments_excluded": True},
        "architecture_question": "PENDING_EXPLICIT_POST_REVIEW_DECISION",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen SPEC-020 credential-semantics human validation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--database", default=str(DEFAULT_DATABASE))
    prepare.add_argument("--config", default=str(DEFAULT_CONFIG))
    prepare.add_argument("--output-root")
    prepare.add_argument("--preparation-id")
    record = subparsers.add_parser("record")
    record.add_argument("preparation_id")
    record.add_argument("--review-number", type=int, required=True)
    record.add_argument("credential_label")
    record.add_argument("consequence_label")
    record.add_argument("--reason", action="append", default=[])
    record.add_argument("--note")
    record.add_argument("--supersedes")
    replace = subparsers.add_parser("replace")
    replace.add_argument("preparation_id")
    replace.add_argument("--review-number", type=int, required=True)
    replace.add_argument("reason")
    report = subparsers.add_parser("report")
    report.add_argument("preparation_id")
    args = parser.parse_args()
    protocol = load_credential_protocol(getattr(args, "config", DEFAULT_CONFIG))
    root = Path(getattr(args, "output_root", None) or protocol.raw["outputs"]["root"])
    if args.command == "prepare":
        result = prepare_credential_validation(
            args.database, args.config, root, preparation_id=args.preparation_id,
        )
        print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))
        return 2 if result["status"].startswith("BLOCKED") else 0
    manifest = load_preparation(root, args.preparation_id)
    judgments_path = protocol.raw["outputs"]["judgments"]
    replacements_path = protocol.raw["outputs"]["replacements"]
    if args.command == "record":
        value = append_judgment(
            manifest, judgments_path, replacements_path, args.credential_label,
            args.consequence_label, review_number=args.review_number,
            reasons=args.reason, note=args.note, supersedes=args.supersedes,
        )
        print(json.dumps({key: value[key] for key in ("record_id", "review_number", "credential_label", "consequence_label")}, indent=2))
        return 0
    if args.command == "replace":
        print(json.dumps(append_replacement(
            manifest, replacements_path, judgments_path, args.review_number, args.reason,
        ), indent=2))
        return 0
    replacements = load_jsonl(replacements_path)
    metrics = calculate_metrics(manifest, load_jsonl(judgments_path), replacements)
    if metrics["status"] != "COMPLETE":
        print(json.dumps(metrics, indent=2))
        return 0
    detailed = root / args.preparation_id / "detailed_report.json"
    if not detailed.exists():
        current = _current_append_only(
            load_jsonl(judgments_path), manifest["preparation_id"], "cluster_id",
        )
        reviewed = []
        for item in effective_selected_items(manifest, replacements):
            judgment = current[item["cluster_id"]]
            reviewed.append({
                "review_number": item["review_number"], "cluster_id": item["cluster_id"],
                "company_id": item["company_id"], "role_family": item["role_family"],
                "credential_wording_pattern": item["credential_wording_pattern"],
                "credential_match": item["credential_match"],
                "qualification_excerpt": item["qualification_excerpt"],
                "credential_label": judgment["credential_label"],
                "consequence_label": judgment["consequence_label"],
                "reasons": judgment["reasons"], "private_note": judgment.get("note"),
            })
        _write_immutable(detailed, json.dumps(
            {"metrics": metrics, "reviewed_items": reviewed}, ensure_ascii=False, indent=2,
        ) + "\n")
    aggregate = build_safe_final_summary(manifest, metrics, judgments_path)
    aggregate_path = root / args.preparation_id / "aggregate_result.json"
    if not aggregate_path.exists():
        _write_immutable(aggregate_path, json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
