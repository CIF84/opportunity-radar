from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from opportunity_radar.change_detection import stable_json
from opportunity_radar.phase3_models import (
    AssessmentConcept, CandidateProfile, DimensionScore,
    OpportunityAssessment, SemanticAssessment,
)
from opportunity_radar.state_repository import StateRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _semantic_from_json(value: str) -> SemanticAssessment:
    raw = json.loads(value)
    dimensions = {key: DimensionScore(**item) for key, item in raw["dimensions"].items()}
    concepts = lambda items: tuple(AssessmentConcept(**item) for item in items)
    return SemanticAssessment(
        dimensions, concepts(raw["strengths"]), concepts(raw["gaps"]), concepts(raw["risks"]),
        raw["assessor_id"], raw["assessor_version"], raw["contract_version"],
    )


class Phase3Repository:
    def __init__(self, state_repository: StateRepository):
        self.state = state_repository

    def save_profile(self, profile: CandidateProfile) -> int:
        payload = {
            "profile": {"profile_id": profile.profile_id, "version": profile.version, "created_at": profile.created_at},
            **profile.semantic_payload(),
            "market_access_policy": profile.market_access_policy.payload(),
            "decision_preferences": profile.decision_preferences.payload(),
            "hard_constraints": profile.hard_constraints,
            "scoring_preferences": {"dimensions": profile.scoring_weights},
        }
        with self.state.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO candidate_profiles(
                   profile_id,profile_version,created_at,full_profile_fingerprint,
                   semantic_profile_fingerprint,scoring_preference_fingerprint,profile_json
                   ) VALUES (?,?,?,?,?,?,?)""",
                (profile.profile_id, profile.version, profile.created_at, profile.full_profile_fingerprint,
                 profile.semantic_profile_fingerprint, profile.scoring_preference_fingerprint, stable_json(payload)),
            )
            row = connection.execute(
                "SELECT candidate_profile_row_id,full_profile_fingerprint FROM candidate_profiles WHERE profile_id=? AND profile_version=?",
                (profile.profile_id, profile.version),
            ).fetchone()
            if row["full_profile_fingerprint"] != profile.full_profile_fingerprint:
                raise ValueError("candidate profile versions are immutable; increment version after changes")
            return row["candidate_profile_row_id"]

    def find_semantic(self, job_instance_id: int, content_fingerprint: str, profile: CandidateProfile, contract_version: str, assessor_id: str, assessor_version: str) -> tuple[int, SemanticAssessment] | None:
        with self.state.connect() as connection:
            row = connection.execute(
                """SELECT semantic_assessment_id,assessment_json FROM semantic_assessments
                   WHERE job_instance_id=? AND content_fingerprint=? AND semantic_profile_fingerprint=?
                   AND semantic_contract_version=? AND assessor_id=? AND assessor_version=?""",
                (job_instance_id, content_fingerprint, profile.semantic_profile_fingerprint,
                 contract_version, assessor_id, assessor_version),
            ).fetchone()
        return (row["semantic_assessment_id"], _semantic_from_json(row["assessment_json"])) if row else None

    def save_semantic(self, job_instance_id: int, job_observation_id: int | None, content_fingerprint: str, profile_row_id: int, profile: CandidateProfile, semantic: SemanticAssessment) -> int:
        with self.state.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO semantic_assessments(
                   job_instance_id,job_observation_id,content_fingerprint,candidate_profile_row_id,
                   semantic_profile_fingerprint,semantic_contract_version,assessor_id,assessor_version,
                   assessment_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (job_instance_id, job_observation_id, content_fingerprint, profile_row_id,
                 profile.semantic_profile_fingerprint, semantic.contract_version,
                 semantic.assessor_id, semantic.assessor_version, stable_json(asdict(semantic)), _now()),
            )
            row = connection.execute(
                """SELECT semantic_assessment_id FROM semantic_assessments WHERE
                   job_instance_id=? AND content_fingerprint=? AND semantic_profile_fingerprint=?
                   AND semantic_contract_version=? AND assessor_id=? AND assessor_version=?""",
                (job_instance_id, content_fingerprint, profile.semantic_profile_fingerprint,
                 semantic.contract_version, semantic.assessor_id, semantic.assessor_version),
            ).fetchone()
            return row["semantic_assessment_id"]

    def save_opportunity(self, job_instance_id: int, job_observation_id: int | None, profile_row_id: int, semantic_id: int | None, profile: CandidateProfile, assessment: OpportunityAssessment, scoring_config_version: str) -> int:
        with self.state.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO opportunity_assessments(
                   job_instance_id,job_observation_id,candidate_profile_row_id,semantic_assessment_id,
                   scoring_preference_fingerprint,scoring_config_version,eligibility_json,features_json,
                   triage_score,composite_score,core_dimension_coverage,assessment_confidence,
                   recommendation,missing_dimensions_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job_instance_id, job_observation_id, profile_row_id, semantic_id,
                 profile.scoring_preference_fingerprint, scoring_config_version,
                 stable_json({
                     "status": assessment.eligibility.status.value,
                     "evidence": [asdict(x) for x in assessment.eligibility.evidence],
                 }), stable_json([asdict(x) for x in assessment.features]),
                 assessment.triage_score, assessment.composite_score, assessment.core_dimension_coverage,
                 assessment.assessment_confidence, assessment.recommendation.value,
                 stable_json(assessment.missing_dimensions), _now()),
            )
            row = connection.execute(
                """SELECT opportunity_assessment_id FROM opportunity_assessments WHERE
                   job_instance_id=? AND job_observation_id IS ? AND candidate_profile_row_id=?
                   AND semantic_assessment_id IS ? AND scoring_preference_fingerprint=? AND scoring_config_version=?""",
                (job_instance_id, job_observation_id, profile_row_id, semantic_id,
                 profile.scoring_preference_fingerprint, scoring_config_version),
            ).fetchone()
            return row["opportunity_assessment_id"]
