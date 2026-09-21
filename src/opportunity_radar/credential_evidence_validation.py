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
from typing import Any, Iterable

import yaml

from opportunity_radar.phase3_config import (
    CandidateProfile,
    Taxonomy,
    digest,
    load_candidate_profile,
    load_taxonomy,
)


DEFAULT_CONFIG = Path("experiments/credential_evidence_semantics_v2.yaml")
DEFAULT_DATABASE = Path("output/opportunity_radar.sqlite3")
DEFAULT_SPEC019_AUDIT = Path(
    "output/stretch_evidence_boundary/spec019-stretch-evidence-20260913-v3/audit.json"
)
DEFAULT_SPEC020_TERMINATION = Path(
    "output/credential_semantics_validation/"
    "spec020-credential-preparation-20260914-v3/aggregate_termination.json"
)
EXPERIMENT_TYPE = "FROZEN_CREDENTIAL_EVIDENCE_SEMANTICS_VALIDATION"


class CredentialEvidenceError(ValueError):
    pass


class EvidenceValidity(str, Enum):
    VALID_FROZEN_EVIDENCE = "VALID_FROZEN_EVIDENCE"
    INSUFFICIENT_CAPTURE = "INSUFFICIENT_CAPTURE"
    PROVEN_SOURCE_CONFLICT = "PROVEN_SOURCE_CONFLICT"
    CORRUPT_OR_INCONSISTENT = "CORRUPT_OR_INCONSISTENT"


class SourceCurrentness(str, Enum):
    SOURCE_CURRENTLY_AVAILABLE = "SOURCE_CURRENTLY_AVAILABLE"
    SOURCE_CURRENTLY_UNAVAILABLE = "SOURCE_CURRENTLY_UNAVAILABLE"
    SOURCE_CURRENTNESS_NOT_CHECKED = "SOURCE_CURRENTNESS_NOT_CHECKED"


SEMANTIC_CLASSES = (
    "EXPLICIT_HARD",
    "DEGREE_OR_EQUIVALENT_EXPERIENCE",
    "PREFERRED_OR_IDEAL",
    "MIXED_MANDATORY_PREFERRED",
    "GENERIC_OR_TEMPLATE",
    "AMBIGUOUS",
    "CONSTITUTIVE_OR_REGULATED",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: str | Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _stable_key(seed: str, *parts: object) -> str:
    return _sha256_bytes(":".join((seed, *(str(part) for part in parts))).encode())


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _compile(value: str, field: str) -> re.Pattern[str]:
    try:
        return re.compile(value, re.I)
    except re.error as exc:
        raise CredentialEvidenceError(f"invalid {field}: {exc}") from exc


def _unique_strings(value: Any, field: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise CredentialEvidenceError(f"{field} must contain unique non-empty strings")
    return tuple(value)


@dataclass(frozen=True)
class CredentialEvidenceProtocol:
    raw: dict[str, Any]
    fingerprint: str
    credential_patterns: dict[str, tuple[re.Pattern[str], ...]]
    regulated_title_patterns: tuple[re.Pattern[str], ...]
    hard_modal_pattern: re.Pattern[str]
    equivalent_experience_pattern: re.Pattern[str]
    preferred_modal_pattern: re.Pattern[str]
    qualification_context_pattern: re.Pattern[str]
    related_requirement_pattern: re.Pattern[str]
    explicit_years_pattern: re.Pattern[str]

    @property
    def experiment_id(self) -> str:
        return str(self.raw["experiment_id"])

    @property
    def preparation_id(self) -> str:
        return str(self.raw["preparation_id"])


@dataclass(frozen=True)
class CredentialEvidenceSnapshot:
    job_instance_id: int
    job_observation_id: int
    company_id: str
    external_job_id: str | None
    employer_name: str
    role_title: str | None
    source: str
    source_url: str | None
    observed_at: str
    retrieved_at: str | None
    exact_credential_statements: tuple[str, ...]
    bounded_qualification_context: str
    exact_modal_terms: tuple[str, ...]
    explicit_year_requirements: tuple[str, ...]
    related_domain_technical_requirements: tuple[str, ...]
    normalized_credential_concept: str
    source_content_fingerprint: str
    evidence_completeness: dict[str, bool]
    evidence_validity: str
    source_currentness: str
    semantic_evidence_class: str
    candidate_substitution_signal: str
    candidate_substitution_evidence: dict[str, Any]
    snapshot_fingerprint: str

    @classmethod
    def create(cls, **values: Any) -> "CredentialEvidenceSnapshot":
        payload = dict(values)
        payload.pop("snapshot_fingerprint", None)
        return cls(**payload, snapshot_fingerprint=digest(payload))

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def load_credential_evidence_protocol(
    path: str | Path = DEFAULT_CONFIG,
) -> CredentialEvidenceProtocol:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version", "protocol_version", "experiment_id", "experiment_type",
        "specification", "preparation_id", "inputs", "evidence",
        "candidate_projection", "sampling", "human_labels", "replacement",
        "privacy", "outputs",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise CredentialEvidenceError("credential evidence protocol has an invalid top-level schema")
    if raw["schema_version"] != 1 or raw["experiment_type"] != EXPERIMENT_TYPE:
        raise CredentialEvidenceError("unsupported credential evidence protocol identity")
    if raw["protocol_version"] != "credential-evidence-semantics-v2":
        raise CredentialEvidenceError("SPEC-021 requires a distinct v2 protocol identity")
    if not str(raw["preparation_id"]).startswith("spec021-"):
        raise CredentialEvidenceError("SPEC-021 preparation id must be explicit and immutable")
    inputs = raw["inputs"]
    if set(inputs) != {"candidate_path", "taxonomy_path", "database_path"}:
        raise CredentialEvidenceError("protocol inputs have an invalid schema")
    for field in ("candidate_path", "taxonomy_path"):
        if not Path(inputs[field]).exists():
            raise CredentialEvidenceError(f"configured input does not exist: {inputs[field]}")

    evidence = raw["evidence"]
    required_evidence = {
        "context_characters_before", "context_characters_after",
        "maximum_context_characters", "maximum_credential_statements",
        "maximum_related_requirements", "credential_patterns",
        "regulated_title_patterns", "hard_modal_pattern",
        "equivalent_experience_pattern", "preferred_modal_pattern",
        "qualification_context_pattern", "related_requirement_pattern",
        "explicit_years_pattern",
    }
    if set(evidence) != required_evidence:
        raise CredentialEvidenceError("evidence configuration has an invalid schema")
    for field in (
        "context_characters_before", "context_characters_after",
        "maximum_context_characters", "maximum_credential_statements",
        "maximum_related_requirements",
    ):
        if not isinstance(evidence[field], int) or evidence[field] <= 0:
            raise CredentialEvidenceError(f"evidence.{field} must be a positive integer")
    if evidence["maximum_context_characters"] < (
        evidence["context_characters_before"] + evidence["context_characters_after"]
    ):
        raise CredentialEvidenceError("bounded context maximum is too small")
    credential_patterns = {
        concept: tuple(_compile(item, f"credential pattern {concept}") for item in patterns)
        for concept, patterns in evidence["credential_patterns"].items()
    }
    if not credential_patterns or any(not patterns for patterns in credential_patterns.values()):
        raise CredentialEvidenceError("credential patterns cannot be empty")

    projection = raw["candidate_projection"]
    if set(projection) != {
        "maximum_role_history_items", "maximum_direct_capabilities",
        "maximum_adjacent_capabilities", "maximum_developing_capabilities",
        "capability_aliases", "relationship_aliases",
    }:
        raise CredentialEvidenceError("candidate projection configuration is invalid")
    for field in (
        "maximum_role_history_items", "maximum_direct_capabilities",
        "maximum_adjacent_capabilities", "maximum_developing_capabilities",
    ):
        if not isinstance(projection[field], int) or projection[field] <= 0:
            raise CredentialEvidenceError(f"candidate_projection.{field} must be positive")
    for mapping_name in ("capability_aliases", "relationship_aliases"):
        for concept, aliases in projection[mapping_name].items():
            _unique_strings(aliases, f"{mapping_name}.{concept}")

    sampling = raw["sampling"]
    if set(sampling) != {
        "seed", "target", "employer_cap", "employer_per_class_cap",
        "reserve_per_class", "class_targets",
    }:
        raise CredentialEvidenceError("sampling configuration is invalid")
    if set(sampling["class_targets"]) != set(SEMANTIC_CLASSES):
        raise CredentialEvidenceError("sampling must target every semantic evidence class")
    if sum(sampling["class_targets"].values()) != sampling["target"]:
        raise CredentialEvidenceError("semantic class targets must sum to sample target")
    if not 30 <= sampling["target"] <= 40:
        raise CredentialEvidenceError("SPEC-021 target must remain approximately 30-40")
    for field in ("target", "employer_cap", "employer_per_class_cap", "reserve_per_class"):
        if not isinstance(sampling[field], int) or sampling[field] <= 0:
            raise CredentialEvidenceError(f"sampling.{field} must be positive")

    labels = raw["human_labels"]
    if set(labels) != {
        "credential_semantics", "experiential_substitution", "independent_capability_gaps",
    }:
        raise CredentialEvidenceError("human label schema is invalid")
    expected_labels = {
        "credential_semantics": {
            "HARD_CREDENTIAL", "DEGREE_OR_EQUIVALENT_EXPERIENCE", "PREFERRED_CREDENTIAL",
            "GENERIC_OR_NONDECISIVE_CREDENTIAL", "AMBIGUOUS_CREDENTIAL",
            "EVIDENCE_CAPTURE_INVALID",
        },
        "experiential_substitution": {
            "EXPERIENCE_STRONGLY_SUBSTITUTES", "EXPERIENCE_PARTIALLY_SUBSTITUTES",
            "NO_CREDIBLE_EXPERIENTIAL_SUBSTITUTE",
            "CREDENTIAL_CONSTITUTIVE_OR_NON_SUBSTITUTABLE", "NEED_MORE_INFORMATION",
        },
        "independent_capability_gaps": {
            "DOMAIN_EXPERTISE_GAP", "TECHNICAL_SKILL_GAP",
            "PROFESSIONAL_FUNCTION_GAP", "REGULATORY_OR_LICENSE_GAP",
            "SENIORITY_DEPTH_GAP", "LANGUAGE_GAP", "OTHER_CAPABILITY_GAP",
        },
    }
    for field, expected_values in expected_labels.items():
        if set(_unique_strings(labels[field], field)) != expected_values:
            raise CredentialEvidenceError(f"{field} vocabulary does not match SPEC-021")
    invalidity = set(_unique_strings(raw["replacement"]["invalidity_reasons"], "invalidity reasons"))
    if invalidity != {
        EvidenceValidity.INSUFFICIENT_CAPTURE.value,
        EvidenceValidity.PROVEN_SOURCE_CONFLICT.value,
        EvidenceValidity.CORRUPT_OR_INCONSISTENT.value,
    }:
        raise CredentialEvidenceError("replacement reasons must be evidence-validity failures")
    if raw["privacy"] != {
        "evidence_manifest": "PRIVATE_LOCAL", "blind_review": "PRIVATE_LOCAL",
        "human_judgments": "PRIVATE_LOCAL_APPEND_ONLY",
        "replacements": "PRIVATE_LOCAL_APPEND_ONLY", "detailed_report": "PRIVATE_LOCAL",
        "aggregate_summary": "REPOSITORY_SAFE",
    }:
        raise CredentialEvidenceError("privacy boundary is invalid")

    return CredentialEvidenceProtocol(
        raw=raw,
        fingerprint=digest(raw),
        credential_patterns=credential_patterns,
        regulated_title_patterns=tuple(
            _compile(item, "regulated title pattern") for item in evidence["regulated_title_patterns"]
        ),
        hard_modal_pattern=_compile(evidence["hard_modal_pattern"], "hard modal pattern"),
        equivalent_experience_pattern=_compile(
            evidence["equivalent_experience_pattern"], "equivalent-experience pattern"
        ),
        preferred_modal_pattern=_compile(evidence["preferred_modal_pattern"], "preferred pattern"),
        qualification_context_pattern=_compile(
            evidence["qualification_context_pattern"], "qualification context pattern"
        ),
        related_requirement_pattern=_compile(
            evidence["related_requirement_pattern"], "related requirement pattern"
        ),
        explicit_years_pattern=_compile(evidence["explicit_years_pattern"], "years pattern"),
    )


def evidence_validity(completeness: dict[str, bool]) -> EvidenceValidity:
    required = {
        "stable_identity", "observation_identity", "observation_timestamp",
        "source_content_fingerprint", "exact_credential_wording", "bounded_context",
    }
    if set(completeness) != required:
        return EvidenceValidity.CORRUPT_OR_INCONSISTENT
    return (
        EvidenceValidity.VALID_FROZEN_EVIDENCE
        if all(completeness.values())
        else EvidenceValidity.INSUFFICIENT_CAPTURE
    )


def evidence_remains_valid_when_currentness_changes(
    snapshot: CredentialEvidenceSnapshot, currentness: SourceCurrentness
) -> bool:
    return (
        snapshot.evidence_validity == EvidenceValidity.VALID_FROZEN_EVIDENCE.value
        and currentness in set(SourceCurrentness)
    )


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    if not text:
        return []
    boundaries = [0]
    boundaries.extend(match.end() for match in re.finditer(r"(?:\n+|(?<=[.!?])\s+)", text))
    boundaries.append(len(text))
    spans: list[tuple[int, int]] = []
    for left, right in zip(boundaries, boundaries[1:]):
        while left < right and text[left].isspace():
            left += 1
        while right > left and text[right - 1].isspace():
            right -= 1
        if right > left:
            spans.append((left, right))
    return spans


def _containing_span(text: str, match: re.Match[str]) -> tuple[int, int]:
    for left, right in _sentence_spans(text):
        if left <= match.start() < right:
            if right - left <= 700:
                return left, right
            return max(left, match.start() - 220), min(right, match.end() + 480)
    return max(0, match.start() - 220), min(len(text), match.end() + 480)


def _all_credential_matches(
    description: str, title: str | None, protocol: CredentialEvidenceProtocol
) -> list[tuple[str, re.Match[str]]]:
    values: list[tuple[str, re.Match[str]]] = []
    for concept, patterns in protocol.credential_patterns.items():
        for pattern in patterns:
            for match in pattern.finditer(description):
                if concept == "PROFESSIONAL_LICENSE":
                    left, right = _containing_span(description, match)
                    nearby = description[max(0, left - 140):min(len(description), right + 140)]
                    if not (
                        protocol.hard_modal_pattern.search(nearby)
                        or protocol.preferred_modal_pattern.search(nearby)
                        or protocol.qualification_context_pattern.search(nearby)
                        or re.search(r"(?i)\\bqualified (?:accountant|lawyer|attorney|physician)\\b", nearby)
                    ):
                        continue
                values.append((concept, match))
    values.sort(key=lambda item: (item[1].start(), item[1].end(), item[0]))
    return values


def _coherent_match_cluster(
    description: str,
    matches: list[tuple[str, re.Match[str]]],
    protocol: CredentialEvidenceProtocol,
) -> list[tuple[str, re.Match[str]]]:
    """Choose one qualification block; do not join distant boilerplate."""
    maximum = int(protocol.raw["evidence"]["maximum_context_characters"])
    clusters: list[list[tuple[str, re.Match[str]]]] = []
    for item in matches:
        if not clusters or item[1].start() - clusters[-1][0][1].start() > maximum - 300:
            clusters.append([item])
        else:
            clusters[-1].append(item)

    def score(cluster: list[tuple[str, re.Match[str]]]) -> tuple[int, int, int, int]:
        left = max(0, cluster[0][1].start() - 250)
        right = min(len(description), cluster[-1][1].end() + 450)
        context = description[left:right]
        return (
            int("PROFESSIONAL_LICENSE" in {item[0] for item in cluster}),
            sum(bool(pattern.search(context)) for pattern in (
                protocol.hard_modal_pattern,
                protocol.equivalent_experience_pattern,
                protocol.preferred_modal_pattern,
                protocol.qualification_context_pattern,
            )),
            len(cluster),
            -cluster[0][1].start(),
        )

    return max(clusters, key=score)


def _bounded_evidence(
    description: str,
    matches: list[tuple[str, re.Match[str]]],
    protocol: CredentialEvidenceProtocol,
    modal_terms: tuple[str, ...],
) -> tuple[tuple[str, ...], str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    config = protocol.raw["evidence"]
    spans: list[tuple[int, int]] = []
    for _, match in matches:
        span = _containing_span(description, match)
        if span not in spans:
            spans.append(span)
    maximum = int(config["maximum_context_characters"])
    bounded_spans: list[tuple[int, int]] = []
    for span in spans[: int(config["maximum_credential_statements"])]:
        proposed = [*bounded_spans, span]
        if max(right for _, right in proposed) - min(left for left, _ in proposed) <= maximum:
            bounded_spans.append(span)
    spans = bounded_spans or [spans[0]]
    statements = tuple(description[left:right] for left, right in spans)
    first = min(left for left, _ in spans)
    last = max(right for _, right in spans)
    spare = maximum - (last - first)
    before = min(int(config["context_characters_before"]), max(0, spare // 2))
    after = min(int(config["context_characters_after"]), max(0, spare - before))
    context_left = max(0, first - before)
    context_right = min(len(description), last + after)
    # Reallocate unused boundary capacity without moving past an exact statement.
    missing = maximum - (context_right - context_left)
    if missing > 0:
        grow_left = min(context_left, missing)
        context_left -= grow_left
        context_right = min(len(description), context_right + missing - grow_left)
    context = description[context_left:context_right].strip()
    if any(statement not in context for statement in statements):
        raise CredentialEvidenceError("bounded context lost exact credential wording")

    years = tuple(dict.fromkeys(
        match.group(0) for match in protocol.explicit_years_pattern.finditer(context)
    ))
    related: list[str] = []
    for left, right in _sentence_spans(context):
        sentence = context[left:right]
        if protocol.related_requirement_pattern.search(sentence) and sentence not in statements:
            related.append(sentence)
        if len(related) >= int(config["maximum_related_requirements"]):
            break
    return statements, context, modal_terms, years, tuple(dict.fromkeys(related))


def _proximal_modals(
    description: str,
    matches: list[tuple[str, re.Match[str]]],
    protocol: CredentialEvidenceProtocol,
) -> tuple[bool, bool, bool, tuple[str, ...]]:
    hard = preferred = equivalent = False
    exact: list[str] = []
    for _, credential in matches:
        left = max(0, credential.start() - 150)
        right = min(len(description), credential.end() + 220)
        nearby = description[left:right]
        for kind, pattern in (
            ("hard", protocol.hard_modal_pattern),
            ("preferred", protocol.preferred_modal_pattern),
            ("equivalent", protocol.equivalent_experience_pattern),
        ):
            for modal in pattern.finditer(nearby):
                # Modal language must belong to the credential clause, not to an
                # unrelated neighboring requirement in flattened source text.
                absolute_start = left + modal.start()
                absolute_end = left + modal.end()
                distance = min(
                    abs(absolute_start - credential.end()),
                    abs(credential.start() - absolute_end),
                )
                distance_limit = 60 if kind == "preferred" else 120
                if distance > distance_limit:
                    continue
                if kind == "preferred":
                    between_left = min(credential.end(), absolute_end)
                    between_right = max(credential.start(), absolute_start)
                    between = description[between_left:between_right]
                    if re.search(
                        r"(?i)\b(?:fluent|language|experience|knowledge|skill|certification)\b",
                        between,
                    ):
                        continue
                    sentence_left, sentence_right = _containing_span(description, credential)
                    if not (sentence_left <= absolute_start < sentence_right):
                        continue
                if kind == "hard":
                    hard = True
                elif kind == "preferred":
                    preferred = True
                else:
                    equivalent = True
                exact.append(modal.group(0))
    return hard, preferred, equivalent, tuple(dict.fromkeys(exact))


def _semantic_evidence_class(
    title: str | None,
    concepts: Iterable[str],
    statements: tuple[str, ...],
    context: str,
    protocol: CredentialEvidenceProtocol,
    *,
    constitutive_required: bool,
    hard: bool,
    preferred: bool,
    equivalent: bool,
) -> str:
    if constitutive_required:
        return "CONSTITUTIVE_OR_REGULATED"
    if hard and preferred:
        return "MIXED_MANDATORY_PREFERRED"
    if equivalent:
        return "DEGREE_OR_EQUIVALENT_EXPERIENCE"
    if preferred:
        return "PREFERRED_OR_IDEAL"
    if hard:
        return "EXPLICIT_HARD"
    prefix = context[: max(0, context.find(statements[0]) + 1)] if statements else context
    blob = "\n".join(statements)
    if protocol.qualification_context_pattern.search(prefix[-350:] + " " + blob[:160]):
        return "GENERIC_OR_TEMPLATE"
    return "AMBIGUOUS"


def _constitutive_requirement(
    description: str,
    title: str | None,
    matches: list[tuple[str, re.Match[str]]],
    protocol: CredentialEvidenceProtocol,
) -> bool:
    if not any(pattern.search(title or "") for pattern in protocol.regulated_title_patterns):
        return False
    for concept, credential in matches:
        if concept not in {"PROFESSIONAL_LICENSE", "DOCTORATE_DEGREE"}:
            continue
        nearby = description[
            max(0, credential.start() - 120):min(len(description), credential.end() + 160)
        ]
        if protocol.hard_modal_pattern.search(nearby) and re.search(
            r"(?i)\b(?:admission|bar|licen[cs]|Juris Doctor|JD|CPA|ACCA|chartered)\b",
            nearby,
        ):
            return True
    return False


def _normalized_credential_concept(concepts: Iterable[str]) -> str:
    priority = (
        "PROFESSIONAL_LICENSE", "DOCTORATE_DEGREE", "MASTERS_DEGREE",
        "BACHELORS_DEGREE", "GENERAL_ACADEMIC_DEGREE",
    )
    values = set(concepts)
    return next((item for item in priority if item in values), sorted(values)[0])


def build_candidate_substitution_projection(
    profile: CandidateProfile,
    taxonomy: Taxonomy,
    job_text: str,
    protocol: CredentialEvidenceProtocol,
) -> dict[str, Any]:
    config = protocol.raw["candidate_projection"]
    lower = job_text.casefold()
    direct: list[dict[str, Any]] = []
    developing: list[dict[str, Any]] = []
    capability_by_id = {item["capability_id"]: item for item in profile.capabilities}
    for concept_id, aliases in config["capability_aliases"].items():
        item = capability_by_id.get(concept_id)
        if item is None:
            continue
        matched = next((alias for alias in aliases if alias.casefold() in lower), None)
        if matched is None:
            continue
        evidence = {
            "capability_id": concept_id,
            "level": item["level"],
            "confidence": item["confidence"],
            "matched_job_term": matched,
            "candidate_source": f"capabilities[{concept_id}]",
        }
        if item["level"] in {"NONE", "BASIC", "DEVELOPING"}:
            developing.append(evidence)
        else:
            direct.append(evidence)

    adjacent: list[dict[str, Any]] = []
    seen_adjacent: set[str] = set()
    for relationship_id, aliases in config["relationship_aliases"].items():
        matched = next((alias for alias in aliases if alias.casefold() in lower), None)
        if matched is None:
            continue
        for related_id in sorted(taxonomy.related(relationship_id) - {relationship_id}):
            item = capability_by_id.get(related_id)
            if item is None or related_id in seen_adjacent:
                continue
            seen_adjacent.add(related_id)
            adjacent.append({
                "capability_id": related_id,
                "level": item["level"],
                "confidence": item["confidence"],
                "via_relationship": relationship_id,
                "matched_job_term": matched,
                "candidate_source": f"capabilities[{related_id}]",
            })

    max_direct = int(config["maximum_direct_capabilities"])
    max_adjacent = int(config["maximum_adjacent_capabilities"])
    max_developing = int(config["maximum_developing_capabilities"])
    values = {
        "completed_bachelors_degree": profile.facts.get("education", {}).get(
            "completed_bachelors_degree"
        ),
        "career_years": dict(profile.facts.get("career", {})),
        "leadership": dict(profile.facts.get("leadership", {})),
        "experience_domains": list(profile.experience.get("domains", [])),
        "role_history_summary": list(profile.experience.get("role_history_summary", []))[
            : int(config["maximum_role_history_items"])
        ],
        "direct_capability_evidence": direct[:max_direct],
        "adjacent_transferable_evidence": adjacent[:max_adjacent],
        "explicit_none_or_developing_evidence": developing[:max_developing],
        "omitted_capability_semantics": "UNKNOWN_NOT_NONE",
    }
    # Preferences and decision_preferences are deliberately outside this projection.
    values["projection_fingerprint"] = digest(values)
    return values


def _candidate_signal(projection: dict[str, Any]) -> str:
    if projection["direct_capability_evidence"]:
        return "DIRECT_MATCH_PRESENT"
    if projection["adjacent_transferable_evidence"]:
        return "ADJACENT_TRANSFERABLE_PRESENT"
    if projection["explicit_none_or_developing_evidence"]:
        return "DEVELOPING_OR_NONE_ONLY"
    return "NO_ASSERTED_MATCH"


def _snapshot_from_row(
    row: sqlite3.Row,
    protocol: CredentialEvidenceProtocol,
    profile: CandidateProfile,
    taxonomy: Taxonomy,
) -> CredentialEvidenceSnapshot | None:
    try:
        normalized = json.loads(row["normalized_snapshot"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise CredentialEvidenceError(
            f"corrupt normalized snapshot for observation {row['job_observation_id']}"
        ) from exc
    description = str(normalized.get("description") or "")
    title = normalized.get("title")
    matches = _all_credential_matches(description, title, protocol)
    if not matches:
        return None
    matches = _coherent_match_cluster(description, matches, protocol)
    hard, preferred, equivalent, modal_terms = _proximal_modals(
        description, matches, protocol
    )
    constitutive_required = _constitutive_requirement(
        description, title, matches, protocol
    )
    statements, context, modals, years, related = _bounded_evidence(
        description, matches, protocol, modal_terms
    )
    concepts = tuple(item[0] for item in matches)
    projection = build_candidate_substitution_projection(
        profile, taxonomy, "\n".join((context, *related)), protocol
    )
    completeness = {
        "stable_identity": bool(row["job_instance_id"] and row["company_id"]),
        "observation_identity": bool(row["job_observation_id"]),
        "observation_timestamp": bool(row["observed_at"]),
        "source_content_fingerprint": bool(row["fingerprint"]),
        "exact_credential_wording": bool(statements),
        "bounded_context": bool(context) and all(item in context for item in statements),
    }
    validity = evidence_validity(completeness)
    values = {
        "job_instance_id": int(row["job_instance_id"]),
        "job_observation_id": int(row["job_observation_id"]),
        "company_id": str(row["company_id"]),
        "external_job_id": row["external_job_id"],
        "employer_name": str(normalized.get("company_name") or row["company_id"]),
        "role_title": title,
        "source": str(normalized.get("source") or "unknown"),
        "source_url": normalized.get("canonical_url") or row["canonical_url"],
        "observed_at": str(row["observed_at"]),
        "retrieved_at": normalized.get("retrieved_at"),
        "exact_credential_statements": statements,
        "bounded_qualification_context": context,
        "exact_modal_terms": modals,
        "explicit_year_requirements": years,
        "related_domain_technical_requirements": related,
        "normalized_credential_concept": _normalized_credential_concept(concepts),
        "source_content_fingerprint": str(row["fingerprint"]),
        "evidence_completeness": completeness,
        "evidence_validity": validity.value,
        "source_currentness": SourceCurrentness.SOURCE_CURRENTNESS_NOT_CHECKED.value,
        "semantic_evidence_class": _semantic_evidence_class(
            title, concepts, statements, context, protocol,
            constitutive_required=constitutive_required,
            hard=hard, preferred=preferred, equivalent=equivalent,
        ),
        "candidate_substitution_signal": _candidate_signal(projection),
        "candidate_substitution_evidence": projection,
    }
    return CredentialEvidenceSnapshot.create(**values)


def build_evidence_population(
    protocol: CredentialEvidenceProtocol,
    database: str | Path = DEFAULT_DATABASE,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    database = Path(database)
    if not database.exists():
        raise CredentialEvidenceError(f"database does not exist: {database}")
    taxonomy = load_taxonomy(protocol.raw["inputs"]["taxonomy_path"])
    profile = load_candidate_profile(protocol.raw["inputs"]["candidate_path"], taxonomy)
    uri = f"file:{database.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    try:
        rows = connection.execute(
            """
            SELECT ji.job_instance_id, ji.company_id, ji.external_job_id,
                   ji.canonical_url, ji.lifecycle_state, ji.latest_observation_id,
                   jo.job_observation_id, jo.observed_at, jo.fingerprint,
                   jo.normalized_snapshot
            FROM job_instances ji
            JOIN job_observations jo ON jo.job_instance_id = ji.job_instance_id
            WHERE jo.normalized_snapshot IS NOT NULL
            ORDER BY ji.job_instance_id, jo.job_observation_id
            """
        ).fetchall()
    finally:
        connection.close()

    # Repeated state runs may preserve the same content as multiple observations.
    # Keep the latest provenance row per job/content fingerprint while retaining
    # genuinely distinct historical content versions.
    unique: dict[tuple[int, str], sqlite3.Row] = {}
    for row in rows:
        unique[(int(row["job_instance_id"]), str(row["fingerprint"]))] = row
    snapshots: list[dict[str, Any]] = []
    invalid_count = 0
    for row in unique.values():
        snapshot = _snapshot_from_row(row, protocol, profile, taxonomy)
        if snapshot is None:
            continue
        payload = snapshot.payload()
        if payload["evidence_validity"] != EvidenceValidity.VALID_FROZEN_EVIDENCE.value:
            invalid_count += 1
            continue
        snapshots.append(payload)
    snapshots.sort(key=lambda item: item["snapshot_fingerprint"])
    latest_ids = {int(row["latest_observation_id"]) for row in rows if row["latest_observation_id"]}
    metadata = {
        "detailed_observation_rows_searched": len(rows),
        "distinct_job_instances_searched": len({int(row["job_instance_id"]) for row in rows}),
        "unique_job_content_versions_searched": len(unique),
        "latest_observation_rows_searched": len(latest_ids),
        "historical_unique_content_versions_searched": sum(
            int(row["job_observation_id"]) not in latest_ids for row in unique.values()
        ),
        "reconstructable_valid_evidence_count": len(snapshots),
        "invalid_or_incomplete_capture_count": invalid_count,
        "semantic_class_distribution": dict(sorted(Counter(
            item["semantic_evidence_class"] for item in snapshots
        ).items())),
        "company_distribution": dict(sorted(Counter(
            item["company_id"] for item in snapshots
        ).items())),
        "credential_concept_distribution": dict(sorted(Counter(
            item["normalized_credential_concept"] for item in snapshots
        ).items())),
        "candidate_substitution_signal_distribution": dict(sorted(Counter(
            item["candidate_substitution_signal"] for item in snapshots
        ).items())),
        "currentness_distribution": dict(sorted(Counter(
            item["source_currentness"] for item in snapshots
        ).items())),
        "evidence_population_fingerprint": digest([
            item["snapshot_fingerprint"] for item in snapshots
        ]),
        "candidate_full_profile_fingerprint": profile.full_profile_fingerprint,
        "candidate_semantic_profile_fingerprint": profile.semantic_profile_fingerprint,
        "candidate_projection_fingerprint": digest([
            item["candidate_substitution_evidence"]["projection_fingerprint"]
            for item in snapshots
        ]),
    }
    return snapshots, metadata


_SELECTION_FIELDS = {
    "snapshot_fingerprint", "semantic_evidence_class", "company_id",
    "normalized_credential_concept", "candidate_substitution_signal",
    "evidence_validity", "source_currentness",
}


def select_semantically_diverse_sample(
    population: list[dict[str, Any]],
    protocol: CredentialEvidenceProtocol,
) -> dict[str, Any]:
    candidates = [
        {key: item[key] for key in _SELECTION_FIELDS}
        for item in population
        if item.get("evidence_validity") == EvidenceValidity.VALID_FROZEN_EVIDENCE.value
    ]
    sampling = protocol.raw["sampling"]
    seed = str(sampling["seed"])
    class_targets = sampling["class_targets"]
    class_counts = Counter(item["semantic_evidence_class"] for item in candidates)
    reserve_count = int(sampling["reserve_per_class"])
    shortages = {
        evidence_class: {
            "available": class_counts[evidence_class],
            "required": int(target) + reserve_count,
        }
        for evidence_class, target in class_targets.items()
        if class_counts[evidence_class] < int(target) + reserve_count
    }
    if shortages:
        raise CredentialEvidenceError(
            f"stored observations cannot support semantic diversity and reserves: {shortages}"
        )

    chosen: list[dict[str, Any]] = []
    company_counts: Counter[str] = Counter()
    per_class_company: Counter[tuple[str, str]] = Counter()
    signal_counts: Counter[str] = Counter()
    concept_counts: Counter[str] = Counter()
    employer_cap = int(sampling["employer_cap"])
    class_employer_cap = int(sampling["employer_per_class_cap"])
    for evidence_class in SEMANTIC_CLASSES:
        target = int(class_targets[evidence_class])
        pool = [item for item in candidates if item["semantic_evidence_class"] == evidence_class]
        for _ in range(target):
            available = [
                item for item in pool
                if item not in chosen
                and company_counts[item["company_id"]] < employer_cap
                and per_class_company[(evidence_class, item["company_id"])] < class_employer_cap
            ]
            if not available:
                raise CredentialEvidenceError(
                    f"semantic class {evidence_class} cannot satisfy diversity caps"
                )
            available.sort(key=lambda item: (
                company_counts[item["company_id"]],
                per_class_company[(evidence_class, item["company_id"])],
                signal_counts[item["candidate_substitution_signal"]],
                concept_counts[item["normalized_credential_concept"]],
                _stable_key(seed, "select", evidence_class, item["snapshot_fingerprint"]),
            ))
            item = available[0]
            chosen.append(item)
            company_counts[item["company_id"]] += 1
            per_class_company[(evidence_class, item["company_id"])] += 1
            signal_counts[item["candidate_substitution_signal"]] += 1
            concept_counts[item["normalized_credential_concept"]] += 1

    selected_fingerprints = {item["snapshot_fingerprint"] for item in chosen}
    reserves: dict[str, list[dict[str, Any]]] = {}
    for evidence_class in SEMANTIC_CLASSES:
        pool = [
            item for item in candidates
            if item["semantic_evidence_class"] == evidence_class
            and item["snapshot_fingerprint"] not in selected_fingerprints
        ]
        pool.sort(key=lambda item: (
            Counter(value["company_id"] for value in chosen)[item["company_id"]],
            _stable_key(seed, "reserve", evidence_class, item["snapshot_fingerprint"]),
        ))
        reserves[evidence_class] = [
            dict(item, reserve_order=index)
            for index, item in enumerate(pool[:reserve_count], 1)
        ]
    if any(len(values) != reserve_count for values in reserves.values()):
        raise CredentialEvidenceError("every semantic class requires frozen invalid-capture reserves")

    chosen.sort(key=lambda item: _stable_key(seed, "blind-order", item["snapshot_fingerprint"]))
    selected = [dict(item, review_number=index) for index, item in enumerate(chosen, 1)]
    return {
        "selected": selected,
        "reserves": reserves,
        "target": int(sampling["target"]),
        "semantic_class_distribution": dict(sorted(Counter(
            item["semantic_evidence_class"] for item in selected
        ).items())),
        "company_distribution": dict(sorted(Counter(
            item["company_id"] for item in selected
        ).items())),
        "credential_concept_distribution": dict(sorted(Counter(
            item["normalized_credential_concept"] for item in selected
        ).items())),
        "candidate_substitution_signal_distribution": dict(sorted(Counter(
            item["candidate_substitution_signal"] for item in selected
        ).items())),
        "selection_fingerprint": digest([
            (item["review_number"], item["snapshot_fingerprint"]) for item in selected
        ]),
        "sample_and_reserve_fingerprint": digest({
            "selected": [item["snapshot_fingerprint"] for item in selected],
            "reserves": {
                key: [item["snapshot_fingerprint"] for item in values]
                for key, values in reserves.items()
            },
        }),
    }


def _snapshot_index(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["snapshot_fingerprint"]: item
        for item in manifest["evidence_population"]["snapshots"]
    }


def render_blind_review(manifest: dict[str, Any]) -> str:
    snapshots = _snapshot_index(manifest)
    lines = [
        f"# Frozen Credential Evidence Review — {manifest['preparation_id']}", "",
        "> Private human-review evidence. Do not commit this file.", "",
        "Judge the captured evidence object. A source page becoming unavailable later does not by itself invalidate the frozen wording.", "",
        "Question A labels: `HARD_CREDENTIAL`, `DEGREE_OR_EQUIVALENT_EXPERIENCE`, `PREFERRED_CREDENTIAL`, `GENERIC_OR_NONDECISIVE_CREDENTIAL`, `AMBIGUOUS_CREDENTIAL`, `EVIDENCE_CAPTURE_INVALID`.", "",
        "Question B labels: `EXPERIENCE_STRONGLY_SUBSTITUTES`, `EXPERIENCE_PARTIALLY_SUBSTITUTES`, `NO_CREDIBLE_EXPERIENTIAL_SUBSTITUTE`, `CREDENTIAL_CONSTITUTIVE_OR_NON_SUBSTITUTABLE`, `NEED_MORE_INFORMATION`.", "",
        "Optional independent gaps: `DOMAIN_EXPERTISE_GAP`, `TECHNICAL_SKILL_GAP`, `PROFESSIONAL_FUNCTION_GAP`, `REGULATORY_OR_LICENSE_GAP`, `SENIORITY_DEPTH_GAP`, `LANGUAGE_GAP`, `OTHER_CAPABILITY_GAP`.", "",
    ]
    for selected in manifest["sample"]["selected"]:
        item = snapshots[selected["snapshot_fingerprint"]]
        candidate = item["candidate_substitution_evidence"]
        lines.extend([
            f"## Review {selected['review_number']}", "",
            f"Employer: {item['employer_name']}", "",
            f"Role: {item['role_title'] or 'Not stated'}", "",
            f"Captured at: {item['observed_at']}", "",
            f"Source currentness: {item['source_currentness']}", "",
            "Exact credential statement(s):", "",
        ])
        lines.extend(f"- {value}" for value in item["exact_credential_statements"])
        lines.extend([
            "", "Bounded qualification context:", "",
            item["bounded_qualification_context"], "",
            "Explicit related requirements:", "",
        ])
        lines.extend(
            [f"- {value}" for value in item["related_domain_technical_requirements"]]
            or ["- None captured"]
        )
        lines.extend([
            "", "Candidate substitution evidence:", "",
            f"- Completed bachelor's degree: {candidate['completed_bachelors_degree']}",
            f"- Career history: {candidate['career_years']}",
            f"- Leadership evidence: {candidate['leadership']}",
        ])
        lines.extend(
            f"- Experience domain: {value['domain_id']} / {value['depth']}"
            for value in candidate["experience_domains"]
        )
        lines.extend(
            f"- Professional history: {value}" for value in candidate["role_history_summary"]
        )
        for key, label in (
            ("direct_capability_evidence", "Direct asserted capability"),
            ("adjacent_transferable_evidence", "Adjacent/transferable capability"),
            ("explicit_none_or_developing_evidence", "Explicit none/developing capability"),
        ):
            lines.extend(
                f"- {label}: {value['capability_id']} / {value['level']} / {value['confidence']}"
                for value in candidate[key]
            )
        lines.extend([
            "", f"Source URL: {item['source_url'] or 'Not available'}", "",
            "Question A: ____________________", "Question B: ____________________",
            "Independent capability gap(s), optional: ____________________",
            "Private note, optional: ____________________", "",
        ])
    text = "\n".join(lines).rstrip() + "\n"
    forbidden = (
        "semantic_evidence_class", "candidate_substitution_signal", "EXCESSIVE_STRETCH",
        "semantic_cache_status", "triage_score", "historical_human_label",
    )
    if any(value.casefold() in text.casefold() for value in forbidden):
        raise CredentialEvidenceError("blind review leaked hidden selection/evaluation evidence")
    return text


def _write_immutable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


def _git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], check=True, capture_output=True, text=True
    ).stdout
    return {
        "commit": commit,
        "dirty": bool(status),
        "worktree_status_fingerprint": _sha256_bytes(status.encode()),
    }


def _safe_aggregate(
    manifest: dict[str, Any], manifest_path: Path, blind_path: Path,
    metadata: dict[str, Any], database_hash: str,
) -> dict[str, Any]:
    selection = manifest["sample"]
    return {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "protocol_version": manifest["protocol_version"],
        "preparation_id": manifest["preparation_id"],
        "status": "PREPARED_AWAITING_HUMAN_REVIEW_APPROVAL",
        "prepared_at": manifest["prepared_at"],
        "source_populations": {
            key: metadata[key] for key in (
                "detailed_observation_rows_searched", "distinct_job_instances_searched",
                "unique_job_content_versions_searched", "latest_observation_rows_searched",
                "historical_unique_content_versions_searched",
                "reconstructable_valid_evidence_count", "invalid_or_incomplete_capture_count",
            )
        },
        "evidence_inventory": {
            "semantic_class_distribution": metadata["semantic_class_distribution"],
            "credential_concept_distribution": metadata["credential_concept_distribution"],
            "candidate_substitution_signal_distribution": metadata[
                "candidate_substitution_signal_distribution"
            ],
            "source_currentness_distribution": metadata["currentness_distribution"],
        },
        "proposed_frozen_sample": {
            "selected_count": len(selection["selected"]),
            "reserve_count": sum(len(values) for values in selection["reserves"].values()),
            "semantic_class_distribution": selection["semantic_class_distribution"],
            "company_distribution": selection["company_distribution"],
            "credential_concept_distribution": selection["credential_concept_distribution"],
            "candidate_substitution_signal_distribution": selection[
                "candidate_substitution_signal_distribution"
            ],
            "selection_fingerprint": selection["selection_fingerprint"],
            "sample_and_reserve_fingerprint": selection["sample_and_reserve_fingerprint"],
            "replacement_policy": "INVALID_OR_INCOMPLETE_EVIDENCE_ONLY_SAME_SEMANTIC_CLASS",
        },
        "fingerprints": {
            "protocol": manifest["protocol_fingerprint"],
            "evidence_population": metadata["evidence_population_fingerprint"],
            "candidate_full_profile": metadata["candidate_full_profile_fingerprint"],
            "candidate_semantic_profile": metadata["candidate_semantic_profile_fingerprint"],
            "candidate_projection": metadata["candidate_projection_fingerprint"],
            "operational_database_sha256": database_hash,
            "private_manifest_sha256": _sha256_file(manifest_path),
            "private_blind_review_sha256": _sha256_file(blind_path),
        },
        "provenance": {
            "git": manifest["git"],
            "database_open_mode": "SQLITE_READ_ONLY_QUERY_ONLY",
            "source_currentness_checked": False,
            "source_currentness_policy": "CURRENTNESS_SEPARATE_FROM_EVIDENCE_VALIDITY",
        },
        "blindness": {
            "selection_excluded_inputs": [
                "candidate_preferences", "recommendation", "semantic_score", "cache_status",
                "stretch_class", "historical_human_labels",
            ],
            "blind_packet_excludes_hidden_semantic_class": True,
            "blind_packet_excludes_runtime_and_historical_labels": True,
        },
        "integrity": {
            "deterministic_selection_replay": True,
            "all_selected_evidence_valid": True,
            "exact_modal_wording_preserved": True,
            "candidate_projection_excludes_preferences": True,
            "operational_database_unchanged": True,
            "sqlite_writes": 0,
            "external_semantic_calls": 0,
            "live_source_calls": 0,
            "human_review_started": False,
            "human_judgments_created": 0,
        },
        "limitations": [
            "The set is deliberately optimized for credential-reasoning coverage, not population prevalence.",
            "Deterministic evidence classes are sampling strata, not human interpretation labels or expected outcomes.",
            "Source currentness was not checked; valid captured evidence remains reviewable after later source decay.",
            "Candidate capability matching is bounded lexical evidence and preserves omitted capability as UNKNOWN.",
            "No runtime credential, stretch, ranking, recommendation, candidate, or source behavior changed.",
        ],
        "conclusion": "Stored current and historical detail supports a semantically diverse immutable evidence set without live or semantic calls; human review remains gated on preparation review and commit.",
    }


def prepare_credential_evidence_validation(
    database: str | Path = DEFAULT_DATABASE,
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    protocol = load_credential_evidence_protocol(config_path)
    database = Path(database)
    before_hash = _sha256_file(database)
    before_mtime = database.stat().st_mtime_ns
    population, metadata = build_evidence_population(protocol, database)
    selection = select_semantically_diverse_sample(population, protocol)
    replay = select_semantically_diverse_sample(population, protocol)
    if selection != replay:
        raise CredentialEvidenceError("semantic coverage selection is not deterministic")
    population_index = {item["snapshot_fingerprint"]: item for item in population}
    manifest = {
        "schema_version": 1,
        "experiment_id": protocol.experiment_id,
        "protocol_version": protocol.raw["protocol_version"],
        "protocol_fingerprint": protocol.fingerprint,
        "preparation_id": protocol.preparation_id,
        "prepared_at": _utc_now(),
        "status": "PREPARED_AWAITING_HUMAN_REVIEW_APPROVAL",
        "git": _git_state(),
        "source_database": {
            "path": str(database), "sha256": before_hash, "open_mode": "READ_ONLY_QUERY_ONLY"
        },
        "human_labels": protocol.raw["human_labels"],
        "replacement": protocol.raw["replacement"],
        "evidence_population": {"metadata": metadata, "snapshots": population},
        "sample": selection,
        "candidate_projection_contract": {
            "includes": [
                "degree_fact", "career_years", "domain_history", "direct_capabilities",
                "adjacent_transferable_capabilities", "explicit_none_or_developing_capabilities",
                "leadership", "role_history",
            ],
            "excludes": ["preferences", "decision_preferences", "recommendation", "semantic_score"],
            "omitted_capability_semantics": "UNKNOWN_NOT_NONE",
        },
        "saturation": {
            "checkpoint_every_substantive_reviews": 10,
            "requires_explicit_human_decision": True,
            "terminal_status": "COMPLETED_REASONING_SATURATION",
        },
    }
    # Resolve every selected/reserve fingerprint before writing immutable files.
    referenced = {
        item["snapshot_fingerprint"] for item in selection["selected"]
    } | {
        item["snapshot_fingerprint"]
        for values in selection["reserves"].values() for item in values
    }
    if referenced - set(population_index):
        raise CredentialEvidenceError("sample references evidence outside the frozen population")

    root = Path(output_root or protocol.raw["outputs"]["root"])
    directory = root / protocol.preparation_id
    manifest_path = directory / "manifest.json"
    blind_path = directory / "blind_review.md"
    aggregate_path = directory / "aggregate_summary.json"
    _write_immutable(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _write_immutable(blind_path, render_blind_review(manifest))
    after_hash = _sha256_file(database)
    after_mtime = database.stat().st_mtime_ns
    if before_hash != after_hash or before_mtime != after_mtime:
        raise CredentialEvidenceError("operational SQLite changed during read-only preparation")
    aggregate = _safe_aggregate(
        manifest, manifest_path, blind_path, metadata, before_hash
    )
    _write_immutable(aggregate_path, json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n")
    return {
        "status": aggregate["status"],
        "manifest": manifest,
        "aggregate": aggregate,
        "paths": {
            "manifest": str(manifest_path),
            "blind_review": str(blind_path),
            "aggregate_summary": str(aggregate_path),
        },
    }


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_jsonl(path: str | Path, value: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _current_records(records: list[dict[str, Any]], key: str) -> dict[Any, dict[str, Any]]:
    superseded = {item.get("supersedes_record_id") for item in records if item.get("supersedes_record_id")}
    return {item[key]: item for item in records if item["record_id"] not in superseded}


def _manifest_for(root: str | Path, preparation_id: str) -> dict[str, Any]:
    path = Path(root) / preparation_id / "manifest.json"
    if not path.exists():
        raise CredentialEvidenceError(f"preparation manifest not found: {preparation_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def effective_selected_items(
    manifest: dict[str, Any], replacements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    selected = {int(item["review_number"]): dict(item) for item in manifest["sample"]["selected"]}
    current = _current_records(
        [item for item in replacements if item["preparation_id"] == manifest["preparation_id"]],
        "review_number",
    )
    for review_number, replacement in current.items():
        selected[int(review_number)]["snapshot_fingerprint"] = replacement[
            "replacement_snapshot_fingerprint"
        ]
        selected[int(review_number)]["replacement_record_id"] = replacement["record_id"]
    return [selected[key] for key in sorted(selected)]


def append_judgment(
    manifest: dict[str, Any],
    judgments_path: str | Path,
    replacements_path: str | Path,
    credential_label: str,
    substitution_label: str,
    *,
    review_number: int,
    independent_gaps: Iterable[str] = (),
    note: str | None = None,
    supersedes: str | None = None,
) -> dict[str, Any]:
    labels = manifest["human_labels"]
    if credential_label not in labels["credential_semantics"]:
        raise CredentialEvidenceError("invalid Question A label")
    if substitution_label not in labels["experiential_substitution"]:
        raise CredentialEvidenceError("invalid Question B label")
    gaps = tuple(independent_gaps)
    invalid_gaps = set(gaps) - set(labels["independent_capability_gaps"])
    if invalid_gaps:
        raise CredentialEvidenceError(f"invalid independent capability gaps: {sorted(invalid_gaps)}")
    if len(gaps) != len(set(gaps)):
        raise CredentialEvidenceError("independent capability gaps cannot repeat")
    replacements = _load_jsonl(replacements_path)
    selected = {
        int(item["review_number"]): item for item in effective_selected_items(manifest, replacements)
    }
    if review_number not in selected:
        raise CredentialEvidenceError("review number is outside the frozen sample")
    records = [
        item for item in _load_jsonl(judgments_path)
        if item["preparation_id"] == manifest["preparation_id"]
    ]
    current = _current_records(records, "review_number").get(review_number)
    if current and supersedes != current["record_id"]:
        raise CredentialEvidenceError(
            f"current judgment exists; supersede {current['record_id']}"
        )
    if supersedes and (current is None or current["record_id"] != supersedes):
        raise CredentialEvidenceError("supersedes must identify the current judgment")
    value = {
        "record_id": str(uuid.uuid4()),
        "preparation_id": manifest["preparation_id"],
        "review_number": review_number,
        "snapshot_fingerprint": selected[review_number]["snapshot_fingerprint"],
        "credential_semantics_label": credential_label,
        "experiential_substitution_label": substitution_label,
        "independent_capability_gaps": list(gaps),
        "note": note,
        "recorded_at": _utc_now(),
        "supersedes_record_id": supersedes,
    }
    _append_jsonl(judgments_path, value)
    return value


def append_invalid_replacement(
    manifest: dict[str, Any],
    replacements_path: str | Path,
    judgments_path: str | Path,
    *,
    review_number: int,
    invalidity_reason: str,
    supersedes: str | None = None,
) -> dict[str, Any]:
    allowed = set(manifest["replacement"]["invalidity_reasons"])
    if invalidity_reason not in allowed:
        raise CredentialEvidenceError("replacement requires a controlled evidence-invalidity reason")
    judgment_current = _current_records(
        [item for item in _load_jsonl(judgments_path) if item["preparation_id"] == manifest["preparation_id"]],
        "review_number",
    )
    if review_number in judgment_current:
        raise CredentialEvidenceError("cannot replace evidence after a human judgment")
    replacements = [
        item for item in _load_jsonl(replacements_path)
        if item["preparation_id"] == manifest["preparation_id"]
    ]
    current = _current_records(replacements, "review_number").get(review_number)
    if current and supersedes != current["record_id"]:
        raise CredentialEvidenceError(f"current replacement exists; supersede {current['record_id']}")
    if supersedes and (current is None or current["record_id"] != supersedes):
        raise CredentialEvidenceError("supersedes must identify the current replacement")
    effective = {int(item["review_number"]): item for item in effective_selected_items(manifest, replacements)}
    if review_number not in effective:
        raise CredentialEvidenceError("review number is outside the frozen sample")
    original = effective[review_number]
    evidence_class = original["semantic_evidence_class"]
    already_used = {item["snapshot_fingerprint"] for item in effective.values()}
    already_used.update(item["replacement_snapshot_fingerprint"] for item in replacements)
    reserve = next((
        item for item in manifest["sample"]["reserves"][evidence_class]
        if item["snapshot_fingerprint"] not in already_used
    ), None)
    if reserve is None:
        raise CredentialEvidenceError("no frozen same-class invalid-capture reserve remains")
    value = {
        "record_id": str(uuid.uuid4()),
        "preparation_id": manifest["preparation_id"],
        "review_number": review_number,
        "original_snapshot_fingerprint": original["snapshot_fingerprint"],
        "replacement_snapshot_fingerprint": reserve["snapshot_fingerprint"],
        "semantic_evidence_class": evidence_class,
        "invalidity_reason": invalidity_reason,
        "recorded_at": _utc_now(),
        "supersedes_record_id": supersedes,
    }
    _append_jsonl(replacements_path, value)
    return value


def calculate_progress(
    manifest: dict[str, Any],
    judgments: list[dict[str, Any]],
    replacements: list[dict[str, Any]],
) -> dict[str, Any]:
    current = _current_records(
        [item for item in judgments if item["preparation_id"] == manifest["preparation_id"]],
        "review_number",
    )
    target = len(manifest["sample"]["selected"])
    substantive = [
        item for item in current.values()
        if item["credential_semantics_label"] != "EVIDENCE_CAPTURE_INVALID"
    ]
    progress: dict[str, Any] = {
        "status": "COMPLETE_PLANNED_COUNT" if len(current) == target else "IN_PROGRESS",
        "reviewed": len(current),
        "substantive_reviewed": len(substantive),
        "target": target,
        "remaining": target - len(current),
    }
    if len(substantive) >= 10 and len(substantive) % 10 == 0:
        patterns = [
            (
                item["credential_semantics_label"],
                item["experiential_substitution_label"],
                tuple(sorted(item["independent_capability_gaps"])),
            )
            for item in sorted(substantive, key=lambda value: value["recorded_at"])
        ]
        earlier = set(patterns[:-10])
        latest = set(patterns[-10:])
        effective = {int(item["review_number"]): item for item in effective_selected_items(manifest, replacements)}
        reviewed_classes = {
            effective[number]["semantic_evidence_class"] for number in current if number in effective
        }
        progress["saturation_checkpoint"] = {
            "substantive_reviews": len(substantive),
            "observed_reasoning_pattern_count": len(set(patterns)),
            "new_patterns_in_last_ten": len(latest - earlier),
            "available_target_coverage_complete": reviewed_classes == set(SEMANTIC_CLASSES),
            "eligible_for_explicit_human_saturation_decision": (
                reviewed_classes == set(SEMANTIC_CLASSES) and not (latest - earlier)
            ),
            "automatic_stop": False,
        }
    return progress


def _count_all(values: Iterable[str], vocabulary: Iterable[str]) -> dict[str, int]:
    counts = Counter(values)
    return {item: int(counts[item]) for item in vocabulary}


def _completed_pairs(
    manifest: dict[str, Any], judgments: list[dict[str, Any]], replacements: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    current = _current_records(
        [item for item in judgments if item["preparation_id"] == manifest["preparation_id"]],
        "review_number",
    )
    effective = effective_selected_items(manifest, replacements)
    if len(current) != len(effective):
        raise CredentialEvidenceError("final analysis requires the complete planned review set")
    snapshots = {
        item["snapshot_fingerprint"]: item
        for item in manifest["evidence_population"]["snapshots"]
    }
    pairs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for selected in effective:
        number = int(selected["review_number"])
        judgment = current.get(number)
        snapshot = snapshots.get(selected["snapshot_fingerprint"])
        if judgment is None or snapshot is None:
            raise CredentialEvidenceError("complete review cannot resolve frozen evidence")
        if judgment["snapshot_fingerprint"] != selected["snapshot_fingerprint"]:
            raise CredentialEvidenceError("judgment does not match effective frozen evidence")
        pairs.append((selected, snapshot, judgment))
    return sorted(pairs, key=lambda item: int(item[0]["review_number"]))


def _reasoning_patterns(
    pairs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    for _, snapshot, judgment in pairs:
        key = (
            judgment["credential_semantics_label"],
            judgment["experiential_substitution_label"],
            tuple(sorted(judgment["independent_capability_gaps"])),
        )
        grouped[key].append(snapshot)
    return [
        {
            "credential_semantics": key[0],
            "experiential_substitution": key[1],
            "independent_capability_gaps": list(key[2]),
            "count": len(items),
            "distinct_employers": len({item["company_id"] for item in items}),
            "distinct_role_contexts": len({
                (item["company_id"], item.get("role_title")) for item in items
            }),
        }
        for key, items in sorted(grouped.items())
    ]


def _semantic_class_coverage(
    pairs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    a_vocab = manifest["human_labels"]["credential_semantics"]
    b_vocab = manifest["human_labels"]["experiential_substitution"]
    for evidence_class in SEMANTIC_CLASSES:
        judgments = [
            judgment for selected, _, judgment in pairs
            if selected["semantic_evidence_class"] == evidence_class
        ]
        result[evidence_class] = {
            "reviewed": len(judgments),
            "question_a_distribution": _count_all(
                (item["credential_semantics_label"] for item in judgments), a_vocab
            ),
            "question_b_distribution": _count_all(
                (item["experiential_substitution_label"] for item in judgments), b_vocab
            ),
        }
    return result


def _spec019_degree_replay(
    manifest: dict[str, Any], spec019_audit_path: str | Path,
) -> dict[str, Any]:
    path = Path(spec019_audit_path)
    if not path.exists():
        raise CredentialEvidenceError("SPEC-019 private audit is required for diagnostic replay")
    audit = json.loads(path.read_text(encoding="utf-8"))
    by_observation = {
        int(item["job_observation_id"]): item
        for item in manifest["evidence_population"]["snapshots"]
    }
    cases: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for item in audit["private_detail"]["current_corpus"]:
        decisive_degree = any(
            requirement["concept_id"] == "bachelors_degree"
            and requirement["gap_severity"] == "DECISIVE"
            for requirement in item["stretch_assessment"]["requirements"]
        )
        if not decisive_degree:
            continue
        snapshot = by_observation.get(int(item["job_observation_id"]))
        if snapshot is None:
            raise CredentialEvidenceError("SPEC-019 degree case lacks frozen v2 evidence")
        cases.append((item, snapshot))
    if len(cases) != 144:
        raise CredentialEvidenceError("SPEC-019 degree-driven corpus identity changed")

    class_counts = Counter(snapshot["semantic_evidence_class"] for _, snapshot in cases)
    concept_counts = Counter(snapshot["normalized_credential_concept"] for _, snapshot in cases)
    normal = [(item, snapshot) for item, snapshot in cases if item["normal_candidate"]]
    constitutive = [
        (item, snapshot) for item, snapshot in cases
        if snapshot["semantic_evidence_class"] == "CONSTITUTIVE_OR_REGULATED"
    ]
    professional_license_candidates = [
        (item, snapshot) for item, snapshot in cases
        if snapshot["normalized_credential_concept"] == "PROFESSIONAL_LICENSE"
    ]
    normal_constitutive = sum(item["normal_candidate"] for item, _ in constitutive)
    normal_license_candidates = sum(
        item["normal_candidate"] for item, _ in professional_license_candidates
    )
    return {
        "source_experiment": audit["experiment_id"],
        "source_run_id": audit["run_id"],
        "source_artifact_sha256": _sha256_file(path),
        "verified_degree_driven_case_count": len(cases),
        "normal_candidate_count": len(normal),
        "already_out_of_scope_count": len(cases) - len(normal),
        "semantic_evidence_class_distribution": dict(sorted(class_counts.items())),
        "credential_concept_distribution": dict(sorted(concept_counts.items())),
        "architecture_a": {
            "degree_driven_capability_excessive": len(cases),
            "normal_candidate_degree_deferrals": len(normal),
        },
        "architecture_b": {
            "degree_driven_capability_excessive": 0,
            "separate_credential_compatibility_objects": len(cases),
            "normal_candidate_compatibility_assessments": len(normal),
        },
        "architecture_c": {
            "high_confidence_constitutive_hard_lower_bound": len(constitutive),
            "professional_license_or_constitutive_candidate_upper_bound": len(
                professional_license_candidates
            ),
            "generic_credential_compatibility_case_range": [
                len(cases) - len(professional_license_candidates),
                len(cases) - len(constitutive),
            ],
            "normal_candidate_constitutive_hard_range": [
                normal_constitutive, normal_license_candidates,
            ],
            "normal_candidate_compatibility_assessment_range": [
                len(normal) - normal_license_candidates,
                len(normal) - normal_constitutive,
            ],
        },
        "interpretation": (
            "Deterministic diagnostic replay on the verified 144-case SPEC-019 corpus; "
            "human-validation sample proportions are not projected onto this population."
        ),
    }


def build_completed_analysis(
    manifest: dict[str, Any], judgments: list[dict[str, Any]], replacements: list[dict[str, Any]],
    *, spec019_audit_path: str | Path = DEFAULT_SPEC019_AUDIT,
    spec020_termination_path: str | Path = DEFAULT_SPEC020_TERMINATION,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pairs = _completed_pairs(manifest, judgments, replacements)
    labels = manifest["human_labels"]
    question_a = _count_all(
        (judgment["credential_semantics_label"] for _, _, judgment in pairs),
        labels["credential_semantics"],
    )
    question_b = _count_all(
        (judgment["experiential_substitution_label"] for _, _, judgment in pairs),
        labels["experiential_substitution"],
    )
    gaps = _count_all(
        (
            gap for _, _, judgment in pairs
            for gap in judgment["independent_capability_gaps"]
        ),
        labels["independent_capability_gaps"],
    )
    patterns = _reasoning_patterns(pairs)
    replay = _spec019_degree_replay(manifest, spec019_audit_path)
    spec020_path = Path(spec020_termination_path)
    if not spec020_path.exists():
        raise CredentialEvidenceError("SPEC-020 termination evidence is required")
    spec020 = json.loads(spec020_path.read_text(encoding="utf-8"))

    substitution_supported = (
        question_b["EXPERIENCE_STRONGLY_SUBSTITUTES"]
        + question_b["EXPERIENCE_PARTIALLY_SUBSTITUTES"]
    )
    constitutive = question_b["CREDENTIAL_CONSTITUTIVE_OR_NON_SUBSTITUTABLE"]
    independent_gap_cases = sum(
        bool(judgment["independent_capability_gaps"]) for _, _, judgment in pairs
    )
    cost_basis = json.loads(Path(spec019_audit_path).read_text(encoding="utf-8"))[
        "fingerprints"
    ]["estimated_cost_per_semantic_call_usd"]
    upper_b_calls = replay["architecture_b"]["normal_candidate_compatibility_assessments"]
    c_call_range = replay["architecture_c"]["normal_candidate_compatibility_assessment_range"]

    safe = {
        "schema_version": 1,
        "artifact_type": "REPOSITORY_SAFE_CREDENTIAL_EVIDENCE_RESULT",
        "experiment_id": manifest["experiment_id"],
        "protocol_version": manifest["protocol_version"],
        "preparation_id": manifest["preparation_id"],
        "status": "COMPLETE_PLANNED_COUNT",
        "coverage": {
            "reviewed": len(pairs),
            "planned": len(manifest["sample"]["selected"]),
            "semantic_classes_covered": len({
                selected["semantic_evidence_class"] for selected, _, _ in pairs
            }),
            "question_a_distribution": question_a,
            "question_b_distribution": question_b,
            "independent_gap_distribution": gaps,
            "cases_with_independent_gaps": independent_gap_cases,
            "reasoning_pattern_count": len(patterns),
            "reasoning_patterns": patterns,
            "semantic_class_coverage": _semantic_class_coverage(pairs, manifest),
            "sampling_interpretation": (
                "Deliberately semantic-class-oversampled human-validation proportions; "
                "not population prevalence estimates."
            ),
        },
        "architecture_comparison": {
            "A_DEGREE_INSIDE_STRETCH": {
                "description": "Current SPEC-019-like treatment keeps degree evidence inside capability stretch.",
                "sample_hard_credential_interpretations": question_a["HARD_CREDENTIAL"],
                "sample_non_hard_interpretations": len(pairs) - question_a["HARD_CREDENTIAL"],
                "degree_driven_capability_excessive_in_verified_corpus": replay["architecture_a"]["degree_driven_capability_excessive"],
                "implication": "Cheap but conflates credential wording, experiential substitution, and independent capability gaps.",
            },
            "B_SEPARATE_CREDENTIAL_COMPATIBILITY": {
                "description": "Capability fit and credential compatibility are separate evidence objects combined only in decision reasoning.",
                "sample_experience_substitution_supported": substitution_supported,
                "sample_no_credible_substitute": question_b["NO_CREDIBLE_EXPERIENTIAL_SUBSTITUTE"],
                "sample_constitutive_or_non_substitutable": constitutive,
                "degree_driven_capability_excessive_in_verified_corpus": 0,
                "separate_credential_objects_in_verified_corpus": replay["architecture_b"]["separate_credential_compatibility_objects"],
                "implication": "Best preserves the observed distinction between credentials and independent capability/domain gaps.",
            },
            "C_CONSTITUTIVE_ONLY_HARD": {
                "description": "Only regulated, licensed, or constitutive credentials remain hard; generic degrees become compatibility evidence.",
                "sample_constitutive_or_non_substitutable": constitutive,
                "sample_non_constitutive": len(pairs) - constitutive,
                "constitutive_hard_case_range_in_verified_corpus": [
                    replay["architecture_c"]["high_confidence_constitutive_hard_lower_bound"],
                    replay["architecture_c"]["professional_license_or_constitutive_candidate_upper_bound"],
                ],
                "generic_compatibility_case_range_in_verified_corpus": replay["architecture_c"]["generic_credential_compatibility_case_range"],
                "implication": "Safest narrow deterministic hard boundary, but requires conservative unresolved handling to avoid false compatibility.",
            },
            "diagnostic_conclusion": (
                "Architecture B is the strongest representation boundary; Architecture C is the narrowest candidate for any future deterministic hard rule. "
                "Neither is promoted by this experiment."
            ),
        },
        "spec020_compatibility": {
            "status": spec020["status"],
            "source_artifact_sha256": _sha256_file(spec020_path),
            "interpretable_cases": spec020["coverage"]["substantively_interpretable_count"],
            "experience_plausibly_substitutes": spec020["coverage"]["interpretable_question_b_label_counts"].get("EXPERIENCE_PLAUSIBLY_SUBSTITUTES", 0),
            "degree_gap_decisive": spec020["coverage"]["interpretable_question_b_label_counts"].get("DEGREE_GAP_DECISIVE", 0),
            "compatible_observations": [
                "Formal credential semantics and practical substitution are distinct judgments.",
                "Independent capability/domain gaps must not be attributed to the degree itself.",
            ],
            "pooling_prohibited": True,
            "reason": "SPEC-020 was incomplete, hard-wording-only, employer-concentrated, and source-decay-confounded.",
        },
        "spec019_diagnostic_replay": replay,
        "compute_allocation": {
            "estimated_semantic_call_cost_usd": cost_basis,
            "architecture_a_incremental_calls": 0,
            "architecture_b_upper_bound_normal_candidate_calls": upper_b_calls,
            "architecture_b_upper_bound_cost_usd": round(upper_b_calls * cost_basis, 8),
            "architecture_c_normal_candidate_call_range": c_call_range,
            "architecture_c_cost_range_usd": [
                round(c_call_range[0] * cost_basis, 8),
                round(c_call_range[1] * cost_basis, 8),
            ],
            "interpretation": (
                "These are conservative call ceilings if every retained normal-candidate credential case receives semantic reasoning. "
                "Deterministic evidence parsing and independent capability checks can reduce calls; no calls were made here."
            ),
        },
        "fingerprints": {
            "protocol": manifest["protocol_fingerprint"],
            "selection": manifest["sample"]["selection_fingerprint"],
            "sample_and_reserves": manifest["sample"]["sample_and_reserve_fingerprint"],
        },
        "integrity": {
            "runtime_behavior_changed": False,
            "semantic_calls": 0,
            "live_source_calls": 0,
            "sqlite_writes": 0,
            "judgments_rewritten": False,
            "population_prevalence_inferred_from_oversampled_validation": False,
        },
        "limitations": [
            "The 36-case sample deliberately oversamples semantic evidence classes and cannot estimate population prevalence.",
            "Question B is candidate-specific and must not be generalized into a universal credential rule.",
            "The SPEC-019 replay is deterministic and diagnostic; lexical evidence classes are not per-case human adjudication.",
            "Architecture call counts are ceilings, not recommended budgets or measured production demand.",
            "No runtime credential, stretch, ranking, recommendation, candidate, or semantic-allocation behavior changed.",
        ],
    }
    detailed = {
        "schema_version": 1,
        "artifact_type": "PRIVATE_CREDENTIAL_EVIDENCE_DETAILED_RESULT",
        "experiment_id": manifest["experiment_id"],
        "preparation_id": manifest["preparation_id"],
        "status": "COMPLETE_PLANNED_COUNT",
        "records": [
            {"selected": selected, "snapshot": snapshot, "judgment": judgment}
            for selected, snapshot, judgment in pairs
        ],
        "safe_analysis": safe,
    }
    return detailed, safe


def run_completed_analysis(
    root: str | Path,
    preparation_id: str,
    judgments_path: str | Path,
    replacements_path: str | Path,
    *,
    spec019_audit_path: str | Path = DEFAULT_SPEC019_AUDIT,
    spec020_termination_path: str | Path = DEFAULT_SPEC020_TERMINATION,
) -> dict[str, Any]:
    directory = Path(root) / preparation_id
    manifest = _manifest_for(Path(root), preparation_id)
    judgment_hash_before = _sha256_file(judgments_path)
    replacement_path = Path(replacements_path)
    replacement_hash_before = _sha256_file(replacement_path) if replacement_path.exists() else None
    detailed, safe = build_completed_analysis(
        manifest,
        _load_jsonl(judgments_path),
        _load_jsonl(replacements_path),
        spec019_audit_path=spec019_audit_path,
        spec020_termination_path=spec020_termination_path,
    )
    detailed_path = directory / "detailed_report.json"
    aggregate_path = directory / "aggregate_result.json"
    detailed_path.write_text(json.dumps(detailed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    safe["fingerprints"].update({
        "private_manifest_sha256": _sha256_file(directory / "manifest.json"),
        "private_judgments_sha256": judgment_hash_before,
        "private_replacements_sha256": replacement_hash_before,
        "private_detailed_report_sha256": _sha256_file(detailed_path),
    })
    aggregate_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if _sha256_file(judgments_path) != judgment_hash_before:
        raise CredentialEvidenceError("final analysis mutated append-only judgments")
    if replacement_path.exists() and _sha256_file(replacement_path) != replacement_hash_before:
        raise CredentialEvidenceError("final analysis mutated append-only replacements")
    return safe


def _load_runtime_paths(protocol: CredentialEvidenceProtocol) -> tuple[Path, Path, Path]:
    output = protocol.raw["outputs"]
    return Path(output["root"]), Path(output["judgments"]), Path(output["replacements"])


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Frozen credential evidence semantics validation v2")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--database", default=str(DEFAULT_DATABASE))
    prepare.add_argument("--output-root")
    record = subparsers.add_parser("record")
    record.add_argument("preparation_id")
    record.add_argument("--review-number", type=int, required=True)
    record.add_argument("credential_label")
    record.add_argument("substitution_label")
    record.add_argument("--gap", action="append", default=[])
    record.add_argument("--note")
    record.add_argument("--supersedes")
    replace = subparsers.add_parser("replace-invalid")
    replace.add_argument("preparation_id")
    replace.add_argument("--review-number", type=int, required=True)
    replace.add_argument("--invalidity", required=True)
    replace.add_argument("--supersedes")
    report = subparsers.add_parser("report")
    report.add_argument("preparation_id")
    return parser


def main() -> int:
    args = _parser().parse_args()
    protocol = load_credential_evidence_protocol(args.config)
    root, judgments, replacements = _load_runtime_paths(protocol)
    if args.command == "prepare":
        result = prepare_credential_evidence_validation(
            args.database,
            config_path=args.config,
            output_root=args.output_root,
        )
        print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2), flush=True)
        return 0
    manifest = _manifest_for(root, args.preparation_id)
    if args.command == "record":
        value = append_judgment(
            manifest, judgments, replacements,
            args.credential_label, args.substitution_label,
            review_number=args.review_number, independent_gaps=args.gap,
            note=args.note, supersedes=args.supersedes,
        )
        print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)
        return 0
    if args.command == "replace-invalid":
        value = append_invalid_replacement(
            manifest, replacements, judgments,
            review_number=args.review_number,
            invalidity_reason=args.invalidity,
            supersedes=args.supersedes,
        )
        print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)
        return 0
    progress = calculate_progress(
        manifest, _load_jsonl(judgments), _load_jsonl(replacements)
    )
    result = (
        run_completed_analysis(root, args.preparation_id, judgments, replacements)
        if progress["status"] == "COMPLETE_PLANNED_COUNT"
        else progress
    )
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
