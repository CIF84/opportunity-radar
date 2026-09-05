from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.phase3_config import (
    Phase3ConfigurationError,
    SENIORITY_GUARD_LEVELS,
    digest,
)
from opportunity_radar.phase3_models import CandidateProfile, Recommendation, SemanticJobInput


DEFAULT_SENIORITY_RULES_PATH = Path("config/seniority_guard_rules.yaml")


class SeniorityGuardReason(str, Enum):
    EXPLICIT_JUNIOR_ROLE = "EXPLICIT_JUNIOR_ROLE"
    EXPLICIT_GRADUATE_ROLE = "EXPLICIT_GRADUATE_ROLE"
    NO_EXPLICIT_DOWNLEVEL_EVIDENCE = "NO_EXPLICIT_DOWNLEVEL_EVIDENCE"
    POLICY_DISABLED = "POLICY_DISABLED"


@dataclass(frozen=True)
class SeniorityEvidence:
    level: str
    source_field: str
    matched_text: str
    rule_id: str
    rule_version: int


@dataclass(frozen=True)
class SeniorityGuardRules:
    rule_id: str
    version: int
    levels: dict[str, dict[str, tuple[str, ...]]]
    fingerprint: str


@dataclass(frozen=True)
class SeniorityGuardAssessment:
    active: bool
    terminal_cap: Recommendation | None
    reason_code: SeniorityGuardReason
    evidence: tuple[SeniorityEvidence, ...]
    configured_levels: tuple[str, ...]
    policy_fingerprint: str
    rules_fingerprint: str
    input_fingerprint: str

    def payload(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "terminal_cap": self.terminal_cap.value if self.terminal_cap else None,
            "reason_code": self.reason_code.value,
            "evidence": [asdict(item) for item in self.evidence],
            "configured_levels": list(self.configured_levels),
            "policy_fingerprint": self.policy_fingerprint,
            "rules_fingerprint": self.rules_fingerprint,
            "input_fingerprint": self.input_fingerprint,
        }


@dataclass(frozen=True)
class SeniorityGuardDecision:
    recommendation_before_guard: Recommendation | None
    recommendation: Recommendation | None
    terminal_cap: Recommendation | None
    cap_applied: bool

    def payload(self) -> dict[str, Any]:
        return {
            "recommendation_before_guard": (
                self.recommendation_before_guard.value
                if self.recommendation_before_guard else None
            ),
            "recommendation": self.recommendation.value if self.recommendation else None,
            "terminal_cap": self.terminal_cap.value if self.terminal_cap else None,
            "cap_applied": self.cap_applied,
        }


def load_seniority_guard_rules(
    path: str | Path = DEFAULT_SENIORITY_RULES_PATH,
) -> SeniorityGuardRules:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"rule_id", "version", "levels"}:
        raise Phase3ConfigurationError("seniority guard rules have an invalid schema")
    if not isinstance(raw["rule_id"], str) or not raw["rule_id"].strip():
        raise Phase3ConfigurationError("seniority guard rule_id must be non-empty")
    if not isinstance(raw["version"], int) or isinstance(raw["version"], bool) or raw["version"] < 1:
        raise Phase3ConfigurationError("seniority guard version must be positive")
    if not isinstance(raw["levels"], dict) or set(raw["levels"]) != SENIORITY_GUARD_LEVELS:
        raise Phase3ConfigurationError("seniority guard rules must define JUNIOR and GRADUATE")
    levels: dict[str, dict[str, tuple[str, ...]]] = {}
    expected = {"title_patterns", "description_patterns", "structured_values"}
    for level, value in raw["levels"].items():
        if not isinstance(value, dict) or set(value) != expected:
            raise Phase3ConfigurationError(f"seniority guard {level} has an invalid schema")
        normalized: dict[str, tuple[str, ...]] = {}
        for field in expected:
            entries = value[field]
            if not isinstance(entries, list) or any(
                not isinstance(item, str) or not item for item in entries
            ):
                raise Phase3ConfigurationError(f"seniority guard {level}.{field} must be a string list")
            if field.endswith("patterns"):
                for pattern in entries:
                    try:
                        re.compile(pattern, re.IGNORECASE)
                    except re.error as exc:
                        raise Phase3ConfigurationError(
                            f"invalid seniority pattern for {level}: {exc}"
                        ) from exc
            normalized[field] = tuple(entries)
        levels[level] = normalized
    return SeniorityGuardRules(
        rule_id=raw["rule_id"],
        version=raw["version"],
        levels=levels,
        fingerprint=digest(raw),
    )


def _explicit_evidence(
    job: SemanticJobInput,
    rules: SeniorityGuardRules,
) -> tuple[SeniorityEvidence, ...]:
    evidence: list[SeniorityEvidence] = []
    for level in ("JUNIOR", "GRADUATE"):
        level_rules = rules.levels[level]
        for source_field, text, patterns in (
            ("title", job.title or "", level_rules["title_patterns"]),
            ("description", job.description or "", level_rules["description_patterns"]),
        ):
            match = None
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    break
            if match:
                evidence.append(SeniorityEvidence(
                    level, source_field, match.group(0), rules.rule_id, rules.version,
                ))
                break
        structured = job.supplemental_evidence.get("seniority")
        if isinstance(structured, str) and structured.casefold() in {
            item.casefold() for item in level_rules["structured_values"]
        }:
            evidence.append(SeniorityEvidence(
                level, "supplemental_evidence.seniority", structured,
                rules.rule_id, rules.version,
            ))
    return tuple(evidence)


def evaluate_seniority_guard(
    job: SemanticJobInput,
    candidate: CandidateProfile,
    rules: SeniorityGuardRules,
) -> SeniorityGuardAssessment:
    policy = candidate.market_access_policy.seniority_guard
    configured = tuple(policy["explicit_levels"])
    evidence = _explicit_evidence(job, rules)
    active_evidence = tuple(item for item in evidence if item.level in configured)
    active = bool(active_evidence)
    if active:
        level = active_evidence[0].level
        reason = (
            SeniorityGuardReason.EXPLICIT_JUNIOR_ROLE
            if level == "JUNIOR" else SeniorityGuardReason.EXPLICIT_GRADUATE_ROLE
        )
    elif not configured:
        reason = SeniorityGuardReason.POLICY_DISABLED
    else:
        reason = SeniorityGuardReason.NO_EXPLICIT_DOWNLEVEL_EVIDENCE
    policy_fingerprint = digest(policy)
    input_payload = {
        "title": job.title,
        "description": job.description,
        "structured_seniority": job.supplemental_evidence.get("seniority"),
        "policy_fingerprint": policy_fingerprint,
        "rules_fingerprint": rules.fingerprint,
    }
    cap = Recommendation(policy["terminal_recommendation_cap"]) if active else None
    return SeniorityGuardAssessment(
        active=active,
        terminal_cap=cap,
        reason_code=reason,
        evidence=evidence,
        configured_levels=configured,
        policy_fingerprint=policy_fingerprint,
        rules_fingerprint=rules.fingerprint,
        input_fingerprint=digest(input_payload),
    )


def apply_seniority_guard(
    recommendation: Recommendation | None,
    assessment: SeniorityGuardAssessment,
) -> SeniorityGuardDecision:
    priority = {
        Recommendation.APPLY: 3,
        Recommendation.REVIEW: 2,
        Recommendation.LOW_PRIORITY: 1,
        Recommendation.INELIGIBLE: 0,
    }
    if not assessment.active or recommendation is None or assessment.terminal_cap is None:
        result = recommendation
    else:
        result = (
            assessment.terminal_cap
            if priority[recommendation] > priority[assessment.terminal_cap]
            else recommendation
        )
    return SeniorityGuardDecision(
        recommendation_before_guard=recommendation,
        recommendation=result,
        terminal_cap=assessment.terminal_cap,
        cap_applied=result is not recommendation,
    )
