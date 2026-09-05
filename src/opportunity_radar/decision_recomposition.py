from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from opportunity_radar.decision_preferences import (
    PreferenceEffectPolicy,
    PreferenceMatchingRules,
    assess_decision_preferences,
)
from opportunity_radar.market_routing import compose_market_routing
from opportunity_radar.market_status import CurrentCandidateMarketAssessment
from opportunity_radar.phase3_models import (
    CandidateProfile,
    DimensionScore,
    EligibilityResult,
    SemanticJobInput,
)
from opportunity_radar.scoring import calculate_composite, derive_recommendation, rank_tier
from opportunity_radar.seniority_guard import (
    SeniorityGuardRules,
    apply_seniority_guard,
    evaluate_seniority_guard,
)


@dataclass(frozen=True)
class RecomposedDecision:
    semantic_identity: dict[str, Any]
    base_composite_score: float | None
    core_dimension_coverage: float
    assessment_confidence: str | None
    missing_dimensions: tuple[str, ...]
    preference_assessment: dict[str, Any]
    decision_adjusted_score: float | None
    tier: str
    recommendation_before_market_policy: str
    market_routing: dict[str, Any]
    seniority_guard: dict[str, Any]
    seniority_guard_decision: dict[str, Any]
    recommendation: str | None

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def _dimensions(payload: dict[str, Any]) -> dict[str, DimensionScore]:
    result: dict[str, DimensionScore] = {}
    for concept_id, value in payload.get("dimensions", {}).items():
        result[str(concept_id)] = DimensionScore(
            score=value.get("score"),
            confidence=str(value["confidence"]),
            reason=str(value["reason"]),
            job_evidence=tuple(value.get("job_evidence", ())),
            candidate_evidence=tuple(value.get("candidate_evidence", ())),
        )
    return result


def recompose_cached_decision(
    job: SemanticJobInput,
    candidate: CandidateProfile,
    semantic_payload: dict[str, Any],
    semantic_identity: dict[str, Any],
    market: CurrentCandidateMarketAssessment,
    eligibility: EligibilityResult,
    preference_policy: PreferenceEffectPolicy,
    preference_rules: PreferenceMatchingRules,
    seniority_rules: SeniorityGuardRules,
) -> RecomposedDecision:
    """Purely recompose current deterministic policy around immutable semantics."""
    composite, coverage, confidence, missing = calculate_composite(
        _dimensions(semantic_payload), candidate.scoring_weights,
    )
    preference = assess_decision_preferences(
        job, semantic_payload, candidate, composite, preference_policy, preference_rules,
    )
    before_market = derive_recommendation(
        eligibility.status.value, preference.decision_adjusted_score,
    )
    routing = compose_market_routing(market.status, eligibility.status, before_market)
    seniority = evaluate_seniority_guard(job, candidate, seniority_rules)
    guarded = apply_seniority_guard(routing.recommendation, seniority)
    return RecomposedDecision(
        semantic_identity=dict(semantic_identity),
        base_composite_score=composite,
        core_dimension_coverage=coverage,
        assessment_confidence=confidence,
        missing_dimensions=missing,
        preference_assessment=preference.payload(),
        decision_adjusted_score=preference.decision_adjusted_score,
        tier=rank_tier(preference.decision_adjusted_score),
        recommendation_before_market_policy=before_market.value,
        market_routing=routing.payload(),
        seniority_guard=seniority.payload(),
        seniority_guard_decision=guarded.payload(),
        recommendation=guarded.recommendation.value if guarded.recommendation else None,
    )
