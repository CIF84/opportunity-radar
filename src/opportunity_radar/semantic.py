from __future__ import annotations

from opportunity_radar.phase3_config import Taxonomy
from opportunity_radar.phase3_models import (
    CORE_DIMENSIONS, AssessmentConcept, DeterministicFeature, DimensionScore,
    SemanticAssessment, SemanticCandidateInput, SemanticJobInput,
)


SEMANTIC_CONTRACT_VERSION = "phase3-semantic-v1"
DIMENSION_RUBRICS = {
    "functional_alignment": "1 unrelated work; 3 mixed alignment; 5 exceptional alignment of responsibilities and preferred work",
    "experience_leverage": "1 little transferable evidence; 3 partial leverage; 5 accumulated experience is central to the role",
    "learning_growth_value": "1 little valuable growth; 3 useful development; 5 unusually valuable capability growth",
    "strategic_alignment": "1 conflicts with configured direction; 3 neutral/mixed; 5 directly advances important goals",
    "seniority_alignment": "1 severe level mismatch; 3 uncertain/mixed; 5 responsibility and scope align exceptionally",
    "application_competitiveness": "1 weak requirement alignment; 3 mixed candidacy; 5 unusually strong evidence against stated requirements",
}
CONFIDENCE_DEFINITIONS = {
    "LOW": "limited or indirect supporting evidence",
    "MEDIUM": "multiple relevant but incomplete evidence points",
    "HIGH": "explicit, directly comparable evidence",
}
LEVEL = {"NONE": 0, "BASIC": 1, "DEVELOPING": 2, "INTERMEDIATE": 3, "ADVANCED": 4, "EXPERT": 5}
REQUIREMENT_CONCEPTS = {
    "sql", "python", "data_engineering", "mysql", "etl_elt", "dbt", "airflow",
    "software_engineering", "programming", "production_software_development", "sdk_development",
    "systems_engineering", "machine_learning", "deep_learning", "pytorch", "jax", "ml_research",
    "model_training", "robotics", "physical_ai", "research_publications", "user_research_methodology",
    "conjoint_analysis", "maxdiff", "discrete_choice", "diary_studies", "moderated_research",
    "unmoderated_research", "bachelors_degree", "consulting_experience",
    "direct_customer_success_practice", "b2b_enterprise_software", "financial_services_domain",
}


class DeterministicSemanticAssessor:
    """Explainable offline assessor for architecture validation, not a trained semantic model."""

    assessor_id = "deterministic-fake"
    assessor_version = "1"

    def __init__(self, taxonomy: Taxonomy):
        self.taxonomy = taxonomy

    @staticmethod
    def _concept(kind: str, concept: str, statement: str, job: str, candidate: str = "") -> AssessmentConcept:
        return AssessmentConcept(kind, concept, statement, "HIGH", "HIGH", (job,), (candidate,) if candidate else ())

    def assess(self, job: SemanticJobInput, candidate: SemanticCandidateInput, features: tuple[DeterministicFeature, ...]) -> SemanticAssessment:
        by_id = {item.concept_id: item for item in features}
        job_concepts = set(by_id)
        caps = {item["capability_id"]: item for item in candidate.capabilities}
        strengths: list[AssessmentConcept] = []
        gaps: list[AssessmentConcept] = []

        candidate_concepts = set(caps)
        for broad in list(job_concepts):
            relation = self.taxonomy.relationships.get(broad, {})
            supports = relation.get("supported_by", [])
            if any(LEVEL[caps[x]["level"]] >= 3 for x in supports if x in caps):
                candidate_concepts.add(broad)

        for concept in sorted(job_concepts):
            capability = caps.get(concept)
            if concept in candidate_concepts and (capability is None or LEVEL[capability["level"]] >= 3):
                source_cap = capability["level"] if capability else "supported by related capabilities"
                strengths.append(self._concept(
                    "strength", concept, f"Candidate evidence supports the job's {concept} demand.",
                    by_id[concept].matched_text, f"{concept}={source_cap}",
                ))
            elif concept in REQUIREMENT_CONCEPTS and capability is not None and LEVEL[capability["level"]] <= 2:
                # An explicit low/NONE assertion is evidence; omission remains UNKNOWN and is not a confirmed gap.
                gaps.append(self._concept(
                    "gap", concept, f"The explicit candidate level is below the apparent {concept} demand.",
                    by_id[concept].matched_text, f"{concept}={capability['level']}",
                ))

        # Explicit factual mismatches are gaps, not eligibility rules.
        if "bachelors_degree" in job_concepts and candidate.facts.get("education", {}).get("completed_bachelors_degree") is False:
            gaps.append(self._concept("gap", "bachelors_degree", "The vacancy requires a degree the candidate explicitly does not hold.", by_id["bachelors_degree"].matched_text, "completed_bachelors_degree=false"))

        risk_ids: list[str] = []
        if job_concepts & {"software_engineering_intensity", "data_engineering", "sql"}:
            risk_ids.append("technical_intensity")
        if "ml_research" in job_concepts:
            risk_ids.extend(["technical_specialization", "research_depth"])
        if "user_research_methodology" in job_concepts and not candidate.capability("user_research_methodology"):
            risk_ids.append("specialist_methodology_depth")
        if "bachelors_degree" in {item.concept_id for item in gaps}:
            risk_ids.append("application_competitiveness")
        if job_concepts & {"financial_services_domain", "b2b_enterprise_software"}:
            candidate_domains = {x["domain_id"] for x in candidate.experience.get("domains", [])}
            demanded_domains = job_concepts & {"financial_services_domain", "fintech_domain", "b2b_enterprise_software"}
            if not (candidate_domains & demanded_domains):
                risk_ids.append("domain_transition")
        if "decentralized_decision_making" in job_concepts:
            risk_ids.extend(["execution_authority", "organizational_structure", "adoption_dependency"])
        if ("software_engineering" in job_concepts or "ml_research" in job_concepts) and not (candidate_concepts & {"software_engineering", "machine_learning", "ml_research"}):
            risk_ids.append("functional_mismatch")
        risks = tuple(self._concept("risk", concept, f"Job evidence indicates {concept.replace('_', ' ')} risk.", next(iter(by_id.values())).matched_text) for concept in dict.fromkeys(risk_ids))

        preferred = {x["characteristic_id"] for x in candidate.preferences.get("role_characteristics", [])}
        goals = {x["goal_id"] for x in candidate.strategic_goals}
        overlap = len(job_concepts & candidate_concepts)
        gap_count = len(gaps)
        technical_role = bool(job_concepts & {"software_engineering", "ml_research"})
        technical_candidate = bool(candidate_concepts & {"software_engineering", "machine_learning", "deep_learning"})
        functional = 2 if technical_role != technical_candidate else min(5, 3 + min(2, overlap // 2))
        if overlap == 0 and not technical_role:
            functional = 3
        experience = min(5, 2 + min(3, overlap // 2))
        if technical_role != technical_candidate:
            experience = 1 if "ml_research" in job_concepts else 2
        learning = 3 + int(bool(gaps or job_concepts & {"ai_enabled_work", "ml_research", "software_engineering"}))
        strategic_matches = len(job_concepts & (preferred | goals))
        if "ai_enabled_career" in goals and "ai_enabled_work" in job_concepts:
            strategic_matches += 2
        if "technical_depth" in goals and technical_role:
            strategic_matches += 2
        strategic = min(5, 3 + min(2, strategic_matches))
        if technical_role and not technical_candidate:
            strategic = min(strategic, 4)
        title = (job.title or "").lower()
        years = int(candidate.facts.get("career", {}).get("total_years", 0))
        if any(x in title for x in ("director", "head", "lead", "manager")):
            seniority = 4 if years >= 8 else 3
        elif any(x in title for x in ("associate", "junior")) and years >= 12:
            seniority = 2
        else:
            seniority = 3
        competitiveness = max(1, min(5, functional - min(2, gap_count)))
        unknown_specialist_requirements = {
            concept for concept in job_concepts & REQUIREMENT_CONCEPTS
            if concept not in caps and concept not in {"bachelors_degree"}
        }
        if unknown_specialist_requirements:
            competitiveness = min(competitiveness, 3)
        if "bachelors_degree" in {item.concept_id for item in gaps}:
            competitiveness = min(competitiveness, 2)

        scores = {
            "functional_alignment": functional,
            "experience_leverage": experience,
            "learning_growth_value": min(5, learning),
            "strategic_alignment": strategic,
            "seniority_alignment": seniority,
            "application_competitiveness": competitiveness,
        }
        dimensions = {
            dimension: DimensionScore(
                score, "MEDIUM", f"Deterministic evidence produced an anchored {score}/5 assessment for {dimension.replace('_', ' ')}.",
                tuple(item.matched_text for item in features[:3]),
                tuple(f"{item['capability_id']}={item['level']}" for item in candidate.capabilities[:3]),
            ) for dimension, score in scores.items()
        }
        assert set(dimensions) == set(CORE_DIMENSIONS)
        return SemanticAssessment(dimensions, tuple(strengths), tuple(gaps), risks, self.assessor_id, self.assessor_version, SEMANTIC_CONTRACT_VERSION)


class FakeSemanticAssessor(DeterministicSemanticAssessor):
    """Explicit spike/test name for the deterministic provider-independent assessor."""


def validate_semantic_assessment(assessment: SemanticAssessment, taxonomy: Taxonomy) -> None:
    if set(assessment.dimensions) != set(CORE_DIMENSIONS):
        raise ValueError("semantic assessment must contain exactly six core dimensions")
    for item in (*assessment.strengths, *assessment.gaps, *assessment.risks):
        if item.kind not in {"strength", "gap", "risk"}:
            raise ValueError(f"invalid assessment concept kind: {item.kind}")
        taxonomy.require(item.concept_id, f"semantic {item.kind}")
