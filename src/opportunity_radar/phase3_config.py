from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.phase3_models import CORE_DIMENSIONS, CandidateProfile


class Phase3ConfigurationError(ValueError):
    pass


CAPABILITY_LEVELS = {"NONE", "BASIC", "DEVELOPING", "INTERMEDIATE", "ADVANCED", "EXPERT"}
CONFIDENCE_LEVELS = {"LOW", "MEDIUM", "HIGH"}
IMPORTANCE_LEVELS = {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}
DOMAIN_DEPTHS = {"LIMITED", "MODERATE", "DEEP"}


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class Taxonomy:
    version: int
    concepts_by_kind: dict[str, frozenset[str]]
    relationships: dict[str, dict[str, Any]]
    deterministic_feature_concepts: frozenset[str]

    @property
    def concepts(self) -> frozenset[str]:
        return frozenset().union(*self.concepts_by_kind.values())

    def require(self, concept_id: str, context: str = "concept") -> None:
        if concept_id not in self.concepts:
            raise Phase3ConfigurationError(f"unknown {context}: {concept_id}")

    def related(self, concept_id: str) -> frozenset[str]:
        relation = self.relationships.get(concept_id, {})
        values = {concept_id}
        for target in relation.values():
            values.update(target if isinstance(target, list) else [target])
        return frozenset(values)


def load_taxonomy(path: str | Path) -> Taxonomy:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("concepts"), dict):
        raise Phase3ConfigurationError("taxonomy must contain concept groups")
    groups = {kind: frozenset(values) for kind, values in raw["concepts"].items()}
    taxonomy = Taxonomy(
        int(raw.get("taxonomy_version", 0)), groups,
        raw.get("relationships", {}),
        frozenset(raw.get("deterministic_feature_concepts", [])),
    )
    for concept, relation in taxonomy.relationships.items():
        taxonomy.require(concept, "relationship concept")
        for value in relation.values():
            for target in value if isinstance(value, list) else [value]:
                taxonomy.require(target, "relationship target")
    for concept in taxonomy.deterministic_feature_concepts:
        taxonomy.require(concept, "deterministic feature concept")
    return taxonomy


def _validate_references(raw: dict[str, Any], taxonomy: Taxonomy) -> None:
    for item in raw["capabilities"]:
        taxonomy.require(item["capability_id"], "candidate capability")
        if item["level"] not in CAPABILITY_LEVELS:
            raise Phase3ConfigurationError(f"invalid capability level: {item['level']}")
        if item["confidence"] not in CONFIDENCE_LEVELS:
            raise Phase3ConfigurationError(f"invalid confidence: {item['confidence']}")
    for item in raw["experience"].get("domains", []):
        taxonomy.require(item["domain_id"], "experience domain")
        if item["depth"] not in DOMAIN_DEPTHS:
            raise Phase3ConfigurationError(f"invalid domain depth: {item['depth']}")
    for item in raw["preferences"].get("sectors", []):
        taxonomy.require(item["sector_id"], "preferred sector")
        if item["importance"] not in IMPORTANCE_LEVELS:
            raise Phase3ConfigurationError("invalid sector importance")
    for item in raw["preferences"].get("role_characteristics", []):
        taxonomy.require(item["characteristic_id"], "role characteristic")
        if item["importance"] not in IMPORTANCE_LEVELS:
            raise Phase3ConfigurationError("invalid role-characteristic importance")
    for item in raw["strategic_goals"]:
        taxonomy.require(item["goal_id"], "strategic goal")
        if item["importance"] not in IMPORTANCE_LEVELS:
            raise Phase3ConfigurationError("invalid strategic-goal importance")


def load_candidate_profile(path: str | Path, taxonomy: Taxonomy) -> CandidateProfile:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required = {"profile", "facts", "capabilities", "experience", "preferences", "hard_constraints", "strategic_goals", "scoring_preferences"}
    if not isinstance(raw, dict) or set(raw) != required:
        raise Phase3ConfigurationError("candidate profile has an invalid top-level schema")
    _validate_references(raw, taxonomy)
    weights = raw["scoring_preferences"].get("dimensions", {})
    if set(weights) != set(CORE_DIMENSIONS):
        raise Phase3ConfigurationError("scoring weights must define exactly the six core dimensions")
    if sum(Decimal(str(value)) for value in weights.values()) != Decimal("1.0"):
        raise Phase3ConfigurationError("scoring weights must sum exactly to 1.0")
    for dimension, value in weights.items():
        taxonomy.require(dimension, "scoring dimension")
        if Decimal(str(value)) < 0:
            raise Phase3ConfigurationError("scoring weights cannot be negative")
    metadata = raw["profile"]
    semantic = {key: raw[key] for key in ("facts", "capabilities", "experience", "preferences", "strategic_goals")}
    return CandidateProfile(
        metadata["profile_id"], int(metadata["version"]), str(metadata["created_at"]),
        raw["facts"], tuple(raw["capabilities"]), raw["experience"], raw["preferences"],
        raw["hard_constraints"], tuple(raw["strategic_goals"]),
        {key: float(value) for key, value in weights.items()},
        digest(raw), digest(semantic), digest(raw["scoring_preferences"]),
    )
