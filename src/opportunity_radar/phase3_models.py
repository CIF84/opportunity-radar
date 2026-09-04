from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Protocol


CORE_DIMENSIONS = (
    "functional_alignment",
    "experience_leverage",
    "learning_growth_value",
    "strategic_alignment",
    "seniority_alignment",
    "application_competitiveness",
)


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNCERTAIN = "UNCERTAIN"


class Recommendation(str, Enum):
    APPLY = "APPLY"
    REVIEW = "REVIEW"
    LOW_PRIORITY = "LOW_PRIORITY"
    INELIGIBLE = "INELIGIBLE"


@dataclass(frozen=True)
class MarketAccessPolicy:
    policy_version: int
    onsite_hybrid: dict[str, Any]
    remote: dict[str, Any]
    relocation: dict[str, Any]
    work_access: dict[str, str]
    languages: dict[str, dict[str, Any]]
    uncertainty: dict[str, Any]
    seniority_guard: dict[str, Any]

    def payload(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "onsite_hybrid": self.onsite_hybrid,
            "remote": self.remote,
            "relocation": self.relocation,
            "work_access": self.work_access,
            "languages": self.languages,
            "uncertainty": self.uncertainty,
            "seniority_guard": self.seniority_guard,
        }

    def work_access_status(self, jurisdiction: str) -> str | None:
        return self.work_access.get(jurisdiction)

    def language_support(self, language: str) -> str | None:
        value = self.languages.get(language)
        return None if value is None else str(value["support"])


@dataclass(frozen=True)
class CandidateProfile:
    profile_id: str
    version: int
    created_at: str
    facts: dict[str, Any]
    capabilities: tuple[dict[str, Any], ...]
    experience: dict[str, Any]
    preferences: dict[str, Any]
    market_access_policy: MarketAccessPolicy
    hard_constraints: dict[str, Any]
    strategic_goals: tuple[dict[str, Any], ...]
    scoring_weights: dict[str, float]
    full_profile_fingerprint: str
    semantic_profile_fingerprint: str
    scoring_preference_fingerprint: str
    market_access_policy_fingerprint: str

    def capability(self, concept_id: str) -> dict[str, Any] | None:
        """None means UNKNOWN; an explicit record may have level NONE."""
        return next((item for item in self.capabilities if item["capability_id"] == concept_id), None)

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "facts": self.facts,
            "capabilities": list(self.capabilities),
            "experience": self.experience,
            "preferences": self.preferences,
            "strategic_goals": list(self.strategic_goals),
        }

    def semantic_input(self) -> "SemanticCandidateInput":
        # Hard constraints belong to deterministic eligibility; weights belong to arithmetic.
        return SemanticCandidateInput(
            self.facts, self.capabilities, self.experience, self.preferences, self.strategic_goals
        )


@dataclass(frozen=True)
class SemanticCandidateInput:
    facts: dict[str, Any]
    capabilities: tuple[dict[str, Any], ...]
    experience: dict[str, Any]
    preferences: dict[str, Any]
    strategic_goals: tuple[dict[str, Any], ...]

    def capability(self, concept_id: str) -> dict[str, Any] | None:
        return next((item for item in self.capabilities if item["capability_id"] == concept_id), None)


@dataclass(frozen=True)
class SemanticJobInput:
    company_name: str
    title: str | None
    description: str
    locations: tuple[dict[str, Any], ...]
    work_mode: str
    employment_type: str | None = None
    department: str | None = None
    supplemental_evidence: dict[str, Any] = field(default_factory=dict)

    def semantic_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EligibilityEvidence:
    rule_id: str
    reason: str
    source_evidence: str | None = None
    candidate_evidence: str | None = None


@dataclass(frozen=True)
class EligibilityResult:
    status: EligibilityStatus
    evidence: tuple[EligibilityEvidence, ...]


@dataclass(frozen=True)
class DeterministicFeature:
    concept_id: str
    matched_text: str
    source_field: str
    rule_version: str


@dataclass(frozen=True)
class DimensionScore:
    score: int | None
    confidence: str
    reason: str
    job_evidence: tuple[str, ...] = ()
    candidate_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.score is not None and self.score not in range(1, 6):
            raise ValueError("dimension score must be an integer from 1 to 5 or null")
        if self.confidence not in {"LOW", "MEDIUM", "HIGH"}:
            raise ValueError("invalid dimension confidence")


@dataclass(frozen=True)
class AssessmentConcept:
    kind: str
    concept_id: str
    statement: str
    importance: str
    confidence: str
    job_evidence: tuple[str, ...] = ()
    candidate_evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class SemanticAssessment:
    dimensions: dict[str, DimensionScore]
    strengths: tuple[AssessmentConcept, ...]
    gaps: tuple[AssessmentConcept, ...]
    risks: tuple[AssessmentConcept, ...]
    assessor_id: str
    assessor_version: str
    contract_version: str


class SemanticAssessor(Protocol):
    assessor_id: str
    assessor_version: str

    def assess(
        self,
        job: SemanticJobInput,
        candidate: SemanticCandidateInput,
        features: tuple[DeterministicFeature, ...],
    ) -> SemanticAssessment: ...


@dataclass(frozen=True)
class OpportunityAssessment:
    eligibility: EligibilityResult
    features: tuple[DeterministicFeature, ...]
    triage_score: int
    semantic: SemanticAssessment | None
    composite_score: float | None
    core_dimension_coverage: float
    assessment_confidence: str | None
    recommendation: Recommendation
    missing_dimensions: tuple[str, ...] = ()
    semantic_reused: bool = False
