from __future__ import annotations

from dataclasses import dataclass

from opportunity_radar.features import extract_features, triage_score
from opportunity_radar.phase3_config import Taxonomy
from opportunity_radar.phase3_models import CandidateProfile, SemanticJobInput


LEVEL = {"NONE": 0, "BASIC": 1, "DEVELOPING": 2, "INTERMEDIATE": 3, "ADVANCED": 4, "EXPERT": 5}
SPECIALIST = {"software_engineering", "ml_research", "data_engineering", "user_research_methodology"}


@dataclass(frozen=True)
class DeterministicBaselineResult:
    score: float | None
    tier: str
    evidence_sufficient: bool
    reasons: tuple[str, ...]
    triage_score: int


def deterministic_baseline(job: SemanticJobInput, candidate: CandidateProfile, taxonomy: Taxonomy) -> DeterministicBaselineResult:
    """Cheap pre-semantic ordering; intentionally not a six-dimension substitute."""
    features = extract_features(job, taxonomy)
    triage = triage_score(features)
    concepts = {x.concept_id for x in features}
    caps = {x["capability_id"]: LEVEL[x["level"]] for x in candidate.capabilities}
    direct_matches = sum(caps.get(concept, -1) >= 3 for concept in concepts)
    explicit_gaps = sum(0 <= caps.get(concept, -1) <= 2 for concept in concepts)
    specialist = concepts & SPECIALIST
    specialist_match = any(caps.get(concept, -1) >= 3 for concept in specialist)
    reasons = [f"triage evidence density={triage}", f"explicit direct matches={direct_matches}", f"explicit low capabilities={explicit_gaps}"]
    score = 2.5 + triage * 0.035 + min(2.5, direct_matches * 0.3) - min(2.0, explicit_gaps * 0.5)
    if specialist and not specialist_match:
        score -= 2.0
        reasons.append("specialist work lacks an explicit matching capability")
    score = round(max(0.0, min(10.0, score)), 2)
    tier = "TOP" if score >= 8 else "HIGH" if score >= 7 else "REVIEW" if score >= 5 else "LOW"
    sufficient = bool(features) and (direct_matches > 0 or bool(specialist))
    return DeterministicBaselineResult(score, tier, sufficient, tuple(reasons), triage)
