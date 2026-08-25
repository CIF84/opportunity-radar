from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from opportunity_radar.phase3_benchmark import BenchmarkCase
from opportunity_radar.phase3_models import CandidateProfile
from opportunity_radar.phase3_pipeline import assess_opportunity
from opportunity_radar.scoring import rank_tier
from opportunity_radar.semantic import DeterministicSemanticAssessor
from opportunity_radar.phase3_config import Taxonomy


QUALITATIVE = {"VERY_WEAK": 1, "WEAK": 2, "MIXED": 3, "STRONG": 4, "VERY_STRONG": 5, "UNKNOWN": None}


@dataclass(frozen=True)
class BenchmarkCaseResult:
    benchmark_id: str
    eligibility: str
    triage_score: int
    composite_score: float | None
    rank_tier: str
    recommendation: str
    eligibility_pass: bool
    rank_pass: bool
    strength_recall: float
    gap_recall: float
    risk_recall: float
    dimension_agreement: float
    notes: tuple[str, ...]


def _recall(expected: list[str], actual: set[str]) -> float:
    return 1.0 if not expected else len(set(expected) & actual) / len(set(expected))


def evaluate_benchmark(cases: list[BenchmarkCase], candidate: CandidateProfile, taxonomy: Taxonomy, assessor: DeterministicSemanticAssessor) -> list[BenchmarkCaseResult]:
    results = []
    for case in cases:
        assessment = assess_opportunity(case.fixture.job, candidate, taxonomy, assessor)
        expected = case.expected
        actual_tier = rank_tier(assessment.composite_score)
        strict_rank = expected.get("job_description_only", {}).get("strict_rank_assertion", True)
        if strict_rank:
            rank_pass = actual_tier == expected["rank_tier"]
        else:
            order = {"LOW": 0, "REVIEW": 1, "HIGH": 2, "TOP": 3}
            minimum = expected["job_description_only"]["expected_minimum_tier"]
            rank_pass = order[actual_tier] >= order[minimum]
        semantic = assessment.semantic
        strengths = {x.concept_id for x in semantic.strengths} if semantic else set()
        gaps = {x.concept_id for x in semantic.gaps} if semantic else set()
        risks = {x.concept_id for x in semantic.risks} if semantic else set()
        dimension_pairs = [
            (QUALITATIVE[label], semantic.dimensions[key].score)
            for key, label in expected["qualitative_dimensions"].items()
            if QUALITATIVE[label] is not None and semantic is not None
        ]
        agreement = sum(abs(a - b) <= 1 for a, b in dimension_pairs) / len(dimension_pairs)
        notes = []
        if not strict_rank:
            notes.append("Final human judgment includes evidence unavailable to job-description-only assessment.")
        results.append(BenchmarkCaseResult(
            case.benchmark_id, assessment.eligibility.status.value, assessment.triage_score,
            assessment.composite_score, actual_tier, assessment.recommendation.value,
            assessment.eligibility.status.value in expected["eligibility"]["allowed"], rank_pass,
            _recall(expected["strengths"]["required_concepts"], strengths),
            _recall(expected["gaps"]["expected_concepts"], gaps),
            _recall(expected["risks"]["expected_categories"], risks), agreement, tuple(notes),
        ))
    return results


def benchmark_summary(results: list[BenchmarkCaseResult], cases: list[BenchmarkCase]) -> dict[str, Any]:
    apply_ids = {case.benchmark_id for case in cases if case.expected["human_decision"] == "APPLY"}
    assessed = {result.benchmark_id for result in results}
    return {
        "case_count": len(results),
        "eligibility_pass_rate": sum(x.eligibility_pass for x in results) / len(results),
        "rank_pass_rate": sum(x.rank_pass for x in results) / len(results),
        "apply_job_triage_recall": len(apply_ids & assessed) / len(apply_ids),
        "mean_strength_recall": sum(x.strength_recall for x in results) / len(results),
        "mean_gap_recall": sum(x.gap_recall for x in results) / len(results),
        "mean_risk_recall": sum(x.risk_recall for x in results) / len(results),
        "mean_dimension_agreement": sum(x.dimension_agreement for x in results) / len(results),
        "cases": [asdict(x) for x in results],
    }
