from __future__ import annotations

from dataclasses import dataclass

from opportunity_radar.phase3_models import CORE_DIMENSIONS, DimensionScore, Recommendation


@dataclass(frozen=True)
class RecommendationConfig:
    apply_minimum: float = 7.0
    review_minimum: float = 5.0


def calculate_composite(dimensions: dict[str, DimensionScore], weights: dict[str, float]) -> tuple[float | None, float, str | None, tuple[str, ...]]:
    missing = tuple(dimension for dimension in CORE_DIMENSIONS if dimension not in dimensions or dimensions[dimension].score is None)
    coverage = (len(CORE_DIMENSIONS) - len(missing)) / len(CORE_DIMENSIONS)
    if missing:
        return None, coverage, None, missing
    weighted = sum(dimensions[key].score * weights[key] for key in CORE_DIMENSIONS)
    radar = round((weighted - 1) * 2.5, 2)
    confidences = [dimensions[key].confidence for key in CORE_DIMENSIONS]
    confidence = "HIGH" if all(x == "HIGH" for x in confidences) else "LOW" if "LOW" in confidences else "MEDIUM"
    return radar, coverage, confidence, ()


def derive_recommendation(eligibility: str, composite: float | None, config: RecommendationConfig = RecommendationConfig()) -> Recommendation:
    if eligibility == "INELIGIBLE":
        return Recommendation.INELIGIBLE
    if composite is None:
        return Recommendation.REVIEW
    if composite >= config.apply_minimum:
        return Recommendation.APPLY
    if composite >= config.review_minimum:
        return Recommendation.REVIEW
    return Recommendation.LOW_PRIORITY


def rank_tier(composite: float | None) -> str:
    if composite is None:
        return "REVIEW"
    if composite >= 8.0:
        return "TOP"
    if composite >= 7.0:
        return "HIGH"
    if composite >= 5.0:
        return "REVIEW"
    return "LOW"
