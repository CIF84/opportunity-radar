from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from opportunity_radar.phase3_config import (
    DECISION_PREFERENCE_STANCES,
    Phase3ConfigurationError,
    Taxonomy,
    digest,
)
from opportunity_radar.phase3_models import (
    CandidateProfile,
    DecisionPreference,
    SemanticAssessment,
    SemanticJobInput,
)
from opportunity_radar.opportunity_clustering import PREFERRED_VARIANT_POLICY_VERSION
from opportunity_radar.scoring import RecommendationConfig


DEFAULT_EFFECT_POLICY_PATH = Path("config/preference_effect_policy.yaml")
DEFAULT_MATCHING_RULES_PATH = Path("config/preference_matching_rules.yaml")


@dataclass(frozen=True)
class PreferenceEffectPolicy:
    policy_id: str
    version: int
    stance_to_effect: dict[str, float]
    aggregate_minimum: float
    aggregate_maximum: float
    score_minimum: float
    score_maximum: float
    fingerprint: str


@dataclass(frozen=True)
class PreferenceMatchingRules:
    rule_id: str
    version: int
    concepts: dict[str, dict[str, tuple[str, ...]]]
    fingerprint: str


@dataclass(frozen=True)
class PreferenceEffect:
    concept_id: str
    source_type: str
    stance: str
    numeric_effect: float
    evidence_source: str
    matched_evidence: str
    candidate_rationale: str | None
    matching_rule_id: str
    matching_rule_version: int


@dataclass(frozen=True)
class PreferenceAssessment:
    matched_effects: tuple[PreferenceEffect, ...]
    raw_total_effect: float
    bounded_total_effect: float
    base_composite_score: float | None
    decision_adjusted_score: float | None
    decision_preference_fingerprint: str
    effect_policy_id: str
    effect_policy_version: int
    effect_policy_fingerprint: str
    matching_rule_id: str
    matching_rule_version: int
    matching_rule_fingerprint: str
    decision_policy_fingerprint: str

    def payload(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "matched_effects": [asdict(item) for item in self.matched_effects],
        }


def _load_mapping(path: str | Path, context: str) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise Phase3ConfigurationError(f"{context} must be a mapping")
    return raw


def load_preference_effect_policy(
    path: str | Path = DEFAULT_EFFECT_POLICY_PATH,
) -> PreferenceEffectPolicy:
    raw = _load_mapping(path, "preference effect policy")
    expected = {
        "policy_id", "version", "stance_to_effect", "aggregate_bounds", "score_bounds",
    }
    if set(raw) != expected:
        raise Phase3ConfigurationError("preference effect policy has an invalid schema")
    if not isinstance(raw["policy_id"], str) or not raw["policy_id"].strip():
        raise Phase3ConfigurationError("preference effect policy_id must be non-empty")
    if not isinstance(raw["version"], int) or isinstance(raw["version"], bool) or raw["version"] < 1:
        raise Phase3ConfigurationError("preference effect policy version must be positive")
    mapping = raw["stance_to_effect"]
    if not isinstance(mapping, dict) or set(mapping) != DECISION_PREFERENCE_STANCES:
        raise Phase3ConfigurationError("preference effect policy must map every stance exactly once")
    aggregate = raw["aggregate_bounds"]
    score = raw["score_bounds"]
    if not isinstance(aggregate, dict) or set(aggregate) != {"minimum", "maximum"}:
        raise Phase3ConfigurationError("aggregate_bounds must define minimum and maximum")
    if not isinstance(score, dict) or set(score) != {"minimum", "maximum"}:
        raise Phase3ConfigurationError("score_bounds must define minimum and maximum")
    values = {key: float(value) for key, value in mapping.items()}
    lower, upper = float(aggregate["minimum"]), float(aggregate["maximum"])
    score_lower, score_upper = float(score["minimum"]), float(score["maximum"])
    if not all(math.isfinite(item) for item in (*values.values(), lower, upper, score_lower, score_upper)):
        raise Phase3ConfigurationError("preference effect policy values must be finite")
    if lower > upper or score_lower > score_upper:
        raise Phase3ConfigurationError("preference effect policy bounds are reversed")
    if values["NEUTRAL"] != 0:
        raise Phase3ConfigurationError("NEUTRAL preference effect must be zero")
    return PreferenceEffectPolicy(
        str(raw["policy_id"]), int(raw["version"]), values,
        lower, upper, score_lower, score_upper, digest(raw),
    )


def load_preference_matching_rules(
    taxonomy: Taxonomy,
    path: str | Path = DEFAULT_MATCHING_RULES_PATH,
) -> PreferenceMatchingRules:
    raw = _load_mapping(path, "preference matching rules")
    if set(raw) != {"matching_rule_id", "version", "concepts"}:
        raise Phase3ConfigurationError("preference matching rules have an invalid schema")
    if not isinstance(raw["matching_rule_id"], str) or not raw["matching_rule_id"].strip():
        raise Phase3ConfigurationError("preference matching rule_id must be non-empty")
    if not isinstance(raw["version"], int) or isinstance(raw["version"], bool) or raw["version"] < 1:
        raise Phase3ConfigurationError("preference matching version must be positive")
    if not isinstance(raw["concepts"], dict):
        raise Phase3ConfigurationError("preference matching concepts must be a mapping")
    concepts: dict[str, dict[str, tuple[str, ...]]] = {}
    for concept_id, value in raw["concepts"].items():
        taxonomy.require(concept_id, "preference matching concept")
        if not isinstance(value, dict) or not {"match_any"} <= set(value) <= {
            "match_any", "exclude_any",
        }:
            raise Phase3ConfigurationError(
                f"preference matcher {concept_id} requires match_any and permits exclude_any"
            )
        rules: dict[str, tuple[str, ...]] = {}
        for field in ("match_any", "exclude_any"):
            patterns = value.get(field, [])
            if not isinstance(patterns, list) or any(not isinstance(item, str) for item in patterns):
                raise Phase3ConfigurationError(f"{concept_id}.{field} must be a string list")
            for pattern in patterns:
                try:
                    re.compile(pattern, re.IGNORECASE)
                except re.error as exc:
                    raise Phase3ConfigurationError(
                        f"invalid preference pattern for {concept_id}: {exc}"
                    ) from exc
            rules[field] = tuple(patterns)
        rules["semantic_concepts"] = tuple(sorted(taxonomy.related(concept_id)))
        concepts[concept_id] = rules
    return PreferenceMatchingRules(
        str(raw["matching_rule_id"]), int(raw["version"]), concepts, digest(raw),
    )


def decision_policy_fingerprint(
    profile: CandidateProfile,
    policy: PreferenceEffectPolicy,
    rules: PreferenceMatchingRules,
) -> str:
    return digest({
        "decision_preference_fingerprint": profile.decision_preference_fingerprint,
        "effect_policy_fingerprint": policy.fingerprint,
        "matching_rule_fingerprint": rules.fingerprint,
        "recommendation_thresholds": asdict(RecommendationConfig()),
        "seniority_guard": profile.market_access_policy.seniority_guard,
        "preferred_variant_policy_version": PREFERRED_VARIANT_POLICY_VERSION,
    })


def _semantic_concepts(semantic: SemanticAssessment | dict[str, Any] | None) -> set[str]:
    if semantic is None:
        return set()
    if isinstance(semantic, SemanticAssessment):
        groups: Iterable[Iterable[Any]] = (semantic.strengths, semantic.gaps, semantic.risks)
        return {item.concept_id for group in groups for item in group}
    return {
        str(item["concept_id"])
        for name in ("strengths", "gaps", "risks")
        for item in semantic.get(name, [])
        if isinstance(item, dict) and item.get("concept_id")
    }


def _match_preference(
    preference: DecisionPreference,
    job: SemanticJobInput,
    semantic_concepts: set[str],
    rules: PreferenceMatchingRules,
) -> tuple[str, str] | None:
    rule = rules.concepts.get(preference.concept_id)
    if rule is None:
        return None
    related = semantic_concepts.intersection(rule["semantic_concepts"])
    if related:
        return "semantic_assessment", sorted(related)[0]
    sources = (("title", job.title or ""), ("description", job.description or ""))
    combined = "\n".join(value for _, value in sources)
    if any(re.search(pattern, combined, re.IGNORECASE) for pattern in rule["exclude_any"]):
        return None
    for source, value in sources:
        for pattern in rule["match_any"]:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                return source, match.group(0)
    return None


def assess_decision_preferences(
    job: SemanticJobInput,
    semantic: SemanticAssessment | dict[str, Any] | None,
    profile: CandidateProfile,
    base_composite_score: float | None,
    policy: PreferenceEffectPolicy,
    rules: PreferenceMatchingRules,
) -> PreferenceAssessment:
    semantic_concepts = _semantic_concepts(semantic)
    effects: list[PreferenceEffect] = []
    for preference in profile.decision_preferences.entries:
        matched = _match_preference(preference, job, semantic_concepts, rules)
        if matched is None:
            continue
        effects.append(PreferenceEffect(
            concept_id=preference.concept_id,
            source_type=preference.source_type,
            stance=preference.stance,
            numeric_effect=policy.stance_to_effect[preference.stance],
            evidence_source=matched[0],
            matched_evidence=matched[1],
            candidate_rationale=preference.rationale,
            matching_rule_id=rules.rule_id,
            matching_rule_version=rules.version,
        ))
    raw_total = round(sum(item.numeric_effect for item in effects), 10)
    bounded = max(policy.aggregate_minimum, min(policy.aggregate_maximum, raw_total))
    adjusted = None
    if base_composite_score is not None:
        adjusted = round(max(
            policy.score_minimum,
            min(policy.score_maximum, base_composite_score + bounded),
        ), 2)
    return PreferenceAssessment(
        matched_effects=tuple(effects),
        raw_total_effect=raw_total,
        bounded_total_effect=bounded,
        base_composite_score=base_composite_score,
        decision_adjusted_score=adjusted,
        decision_preference_fingerprint=profile.decision_preference_fingerprint,
        effect_policy_id=policy.policy_id,
        effect_policy_version=policy.version,
        effect_policy_fingerprint=policy.fingerprint,
        matching_rule_id=rules.rule_id,
        matching_rule_version=rules.version,
        matching_rule_fingerprint=rules.fingerprint,
        decision_policy_fingerprint=decision_policy_fingerprint(profile, policy, rules),
    )
