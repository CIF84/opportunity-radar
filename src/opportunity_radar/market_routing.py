from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from opportunity_radar.eligibility import evaluate_eligibility
from opportunity_radar.market_status import (
    CurrentCandidateMarketAssessment,
    CurrentCandidateMarketStatus,
    MarketNormalizationRules,
    evaluate_current_candidate_market,
)
from opportunity_radar.phase3_config import Taxonomy
from opportunity_radar.phase3_models import (
    CandidateProfile,
    EligibilityResult,
    EligibilityStatus,
    OpportunityAssessment,
    Recommendation,
    SemanticAssessor,
    SemanticJobInput,
)
from opportunity_radar.phase3_pipeline import assess_opportunity
from opportunity_radar.phase3_repository import Phase3Repository
from opportunity_radar.scoring import RecommendationConfig


class MarketRoutingReason(str, Enum):
    NORMAL_MARKET_FLOW = "NORMAL_MARKET_FLOW"
    OUT_OF_SCOPE_EXCLUDED = "OUT_OF_SCOPE_EXCLUDED"
    HARD_INELIGIBLE_EXCLUDED = "HARD_INELIGIBLE_EXCLUDED"
    UNCERTAIN_RECOMMENDATION_CAPPED = "UNCERTAIN_RECOMMENDATION_CAPPED"
    UNCERTAIN_WITHIN_CAP = "UNCERTAIN_WITHIN_CAP"


@dataclass(frozen=True)
class CandidateMarketRoutingDecision:
    market_status: CurrentCandidateMarketStatus
    hard_eligibility: EligibilityStatus
    include_in_normal_shortlist: bool
    eligible_for_semantic_processing: bool
    recommendation_before_market_policy: Recommendation | None
    recommendation: Recommendation | None
    recommendation_cap: Recommendation | None
    cap_applied: bool
    reason: MarketRoutingReason

    def payload(self) -> dict[str, object]:
        return {
            "market_status": self.market_status.value,
            "hard_eligibility": self.hard_eligibility.value,
            "include_in_normal_shortlist": self.include_in_normal_shortlist,
            "eligible_for_semantic_processing": self.eligible_for_semantic_processing,
            "recommendation_before_market_policy": (
                self.recommendation_before_market_policy.value
                if self.recommendation_before_market_policy else None
            ),
            "recommendation": self.recommendation.value if self.recommendation else None,
            "recommendation_cap": (
                self.recommendation_cap.value if self.recommendation_cap else None
            ),
            "cap_applied": self.cap_applied,
            "reason": self.reason.value,
        }


@dataclass(frozen=True)
class RoutedOpportunityAssessment:
    market: CurrentCandidateMarketAssessment
    eligibility: EligibilityResult
    routing: CandidateMarketRoutingDecision
    opportunity: OpportunityAssessment | None


def compose_market_routing(
    market_status: CurrentCandidateMarketStatus,
    hard_eligibility: EligibilityStatus,
    recommendation: Recommendation | None = None,
) -> CandidateMarketRoutingDecision:
    """Compose deterministic market, eligibility, and terminal recommendation policy."""
    if market_status is CurrentCandidateMarketStatus.OUT_OF_SCOPE:
        return CandidateMarketRoutingDecision(
            market_status,
            hard_eligibility,
            include_in_normal_shortlist=False,
            eligible_for_semantic_processing=False,
            recommendation_before_market_policy=recommendation,
            recommendation=None,
            recommendation_cap=None,
            cap_applied=False,
            reason=MarketRoutingReason.OUT_OF_SCOPE_EXCLUDED,
        )
    if hard_eligibility is EligibilityStatus.INELIGIBLE:
        return CandidateMarketRoutingDecision(
            market_status,
            hard_eligibility,
            include_in_normal_shortlist=False,
            eligible_for_semantic_processing=False,
            recommendation_before_market_policy=recommendation,
            recommendation=Recommendation.INELIGIBLE,
            recommendation_cap=None,
            cap_applied=False,
            reason=MarketRoutingReason.HARD_INELIGIBLE_EXCLUDED,
        )
    if market_status is CurrentCandidateMarketStatus.UNCERTAIN:
        capped = Recommendation.REVIEW if recommendation is Recommendation.APPLY else recommendation
        return CandidateMarketRoutingDecision(
            market_status,
            hard_eligibility,
            include_in_normal_shortlist=True,
            eligible_for_semantic_processing=True,
            recommendation_before_market_policy=recommendation,
            recommendation=capped,
            recommendation_cap=Recommendation.REVIEW,
            cap_applied=recommendation is Recommendation.APPLY,
            reason=(
                MarketRoutingReason.UNCERTAIN_RECOMMENDATION_CAPPED
                if recommendation is Recommendation.APPLY
                else MarketRoutingReason.UNCERTAIN_WITHIN_CAP
            ),
        )
    return CandidateMarketRoutingDecision(
        market_status,
        hard_eligibility,
        include_in_normal_shortlist=True,
        eligible_for_semantic_processing=True,
        recommendation_before_market_policy=recommendation,
        recommendation=recommendation,
        recommendation_cap=None,
        cap_applied=False,
        reason=MarketRoutingReason.NORMAL_MARKET_FLOW,
    )


def assess_routed_opportunity(
    job: SemanticJobInput,
    candidate: CandidateProfile,
    taxonomy: Taxonomy,
    assessor: SemanticAssessor,
    market_rules: MarketNormalizationRules,
    *,
    repository: Phase3Repository | None = None,
    job_instance_id: int | None = None,
    job_observation_id: int | None = None,
    content_fingerprint: str | None = None,
    recommendation_config: RecommendationConfig = RecommendationConfig(),
) -> RoutedOpportunityAssessment:
    """Shared candidate-ranking boundary; OUT_OF_SCOPE exits before semantics."""
    market = evaluate_current_candidate_market(job, candidate, market_rules)
    eligibility = evaluate_eligibility(job, candidate)
    initial = compose_market_routing(market.status, eligibility.status)
    if market.status is CurrentCandidateMarketStatus.OUT_OF_SCOPE:
        return RoutedOpportunityAssessment(market, eligibility, initial, None)

    opportunity = assess_opportunity(
        job,
        candidate,
        taxonomy,
        assessor,
        repository=repository,
        job_instance_id=job_instance_id,
        job_observation_id=job_observation_id,
        content_fingerprint=content_fingerprint,
        recommendation_config=recommendation_config,
    )
    routing = compose_market_routing(
        market.status, opportunity.eligibility.status, opportunity.recommendation,
    )
    if routing.recommendation is not opportunity.recommendation:
        opportunity = replace(opportunity, recommendation=routing.recommendation)
    return RoutedOpportunityAssessment(market, opportunity.eligibility, routing, opportunity)
