from __future__ import annotations

from dataclasses import replace

from opportunity_radar.eligibility import evaluate_eligibility
from opportunity_radar.features import extract_features, triage_score
from opportunity_radar.phase3_config import Taxonomy
from opportunity_radar.phase3_models import CandidateProfile, EligibilityStatus, OpportunityAssessment, SemanticAssessor, SemanticJobInput
from opportunity_radar.phase3_repository import Phase3Repository
from opportunity_radar.scoring import RecommendationConfig, calculate_composite, derive_recommendation
from opportunity_radar.semantic import SEMANTIC_CONTRACT_VERSION, validate_semantic_assessment


SCORING_CONFIG_VERSION = "phase3-scoring-v1"


def assess_opportunity(
    job: SemanticJobInput,
    candidate: CandidateProfile,
    taxonomy: Taxonomy,
    assessor: SemanticAssessor,
    *,
    repository: Phase3Repository | None = None,
    job_instance_id: int | None = None,
    job_observation_id: int | None = None,
    content_fingerprint: str | None = None,
    recommendation_config: RecommendationConfig = RecommendationConfig(),
) -> OpportunityAssessment:
    eligibility = evaluate_eligibility(job, candidate)
    features = extract_features(job, taxonomy)
    triage = triage_score(features)
    if eligibility.status == EligibilityStatus.INELIGIBLE:
        result = OpportunityAssessment(
            eligibility, features, triage, None, None, 0.0, None,
            derive_recommendation(eligibility.status.value, None, recommendation_config),
        )
        return result

    profile_row_id = semantic_id = None
    semantic = None
    reused = False
    if repository is not None:
        if job_instance_id is None or content_fingerprint is None:
            raise ValueError("persistent assessment requires job identity and content fingerprint")
        profile_row_id = repository.save_profile(candidate)
        cached = repository.find_semantic(
            job_instance_id, content_fingerprint, candidate, SEMANTIC_CONTRACT_VERSION,
            assessor.assessor_id, assessor.assessor_version,
        )
        if cached:
            semantic_id, semantic = cached
            reused = True
    if semantic is None:
        semantic = assessor.assess(job, candidate.semantic_input(), features)
        validate_semantic_assessment(semantic, taxonomy)
        if repository is not None:
            semantic_id = repository.save_semantic(
                job_instance_id, job_observation_id, content_fingerprint,
                profile_row_id, candidate, semantic,
            )
    composite, coverage, confidence, missing = calculate_composite(semantic.dimensions, candidate.scoring_weights)
    result = OpportunityAssessment(
        eligibility, features, triage, semantic, composite, coverage, confidence,
        derive_recommendation(eligibility.status.value, composite, recommendation_config),
        missing, reused,
    )
    if repository is not None:
        repository.save_opportunity(
            job_instance_id, job_observation_id, profile_row_id, semantic_id,
            candidate, result, SCORING_CONFIG_VERSION,
        )
    return result
