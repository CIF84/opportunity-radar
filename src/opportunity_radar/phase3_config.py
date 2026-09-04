from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.phase3_models import CORE_DIMENSIONS, CandidateProfile, MarketAccessPolicy


class Phase3ConfigurationError(ValueError):
    pass


CAPABILITY_LEVELS = {"NONE", "BASIC", "DEVELOPING", "INTERMEDIATE", "ADVANCED", "EXPERT"}
CONFIDENCE_LEVELS = {"LOW", "MEDIUM", "HIGH"}
IMPORTANCE_LEVELS = {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}
DOMAIN_DEPTHS = {"LIMITED", "MODERATE", "DEEP"}
MARKET_SCOPE_STATUSES = {"IN_SCOPE", "UNCERTAIN", "OUT_OF_SCOPE"}
WORK_ACCESS_STATUSES = {"CONFIRMED", "INCOMPATIBLE", "UNKNOWN"}
RELOCATION_MODES = {"NORMAL", "EXCEPTIONAL_ONLY", "PROHIBITED", "UNKNOWN"}
LANGUAGE_SUPPORT_LEVELS = {
    "NATIVE_PROFESSIONAL", "PROFESSIONAL", "COMPREHENSION_ONLY", "NONE", "UNKNOWN",
}
REMOTE_SCOPE_LABELS = {
    "CZECHIA", "EUROPE", "EUROPEAN_UNION", "EUROPEAN_ECONOMIC_AREA", "GLOBAL",
}
WORKING_TIME_REGIONS = {
    "EUROPEAN_COMPATIBLE", "NORTH_AMERICAN_COMPATIBLE",
    "ASIA_PACIFIC_COMPATIBLE", "GLOBAL_FLEXIBLE",
}
SENIORITY_GUARD_LEVELS = {"JUNIOR", "GRADUATE"}


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


def _mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Phase3ConfigurationError(f"{context} must be a mapping")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise Phase3ConfigurationError(f"{context} must define exactly {sorted(expected)}")


def _string_list(value: Any, context: str, allowed: set[str]) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise Phase3ConfigurationError(f"{context} must be a list of controlled values")
    if len(set(value)) != len(value):
        raise Phase3ConfigurationError(f"{context} contains duplicate values")
    invalid = set(value) - allowed
    if invalid:
        raise Phase3ConfigurationError(f"invalid {context}: {sorted(invalid)}")
    return value


def _validate_market_access_policy(raw: Any) -> MarketAccessPolicy:
    policy = _mapping(raw, "market_access_policy")
    _exact_keys(
        policy,
        {
            "policy_version", "onsite_hybrid", "remote", "relocation",
            "work_access", "languages", "uncertainty", "seniority_guard",
        },
        "market_access_policy",
    )
    version = policy["policy_version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise Phase3ConfigurationError("market_access_policy.policy_version must be a positive integer")

    onsite = _mapping(policy["onsite_hybrid"], "market_access_policy.onsite_hybrid")
    _exact_keys(
        onsite, {"accepted_locations", "outside_accepted_locations"},
        "market_access_policy.onsite_hybrid",
    )
    locations = onsite["accepted_locations"]
    if not isinstance(locations, list):
        raise Phase3ConfigurationError("market_access_policy.onsite_hybrid.accepted_locations must be a list")
    for index, location in enumerate(locations):
        location = _mapping(location, f"accepted_locations[{index}]")
        if not set(location) <= {"country", "city", "region"} or "country" not in location:
            raise Phase3ConfigurationError(
                "accepted locations require country and may contain city/region"
            )
        if any(not isinstance(value, str) or not value.strip() for value in location.values()):
            raise Phase3ConfigurationError("accepted location values must be non-empty strings")
    if onsite["outside_accepted_locations"] not in MARKET_SCOPE_STATUSES:
        raise Phase3ConfigurationError("invalid outside_accepted_locations status")

    remote = _mapping(policy["remote"], "market_access_policy.remote")
    _exact_keys(
        remote,
        {
            "residence_country", "require_confirmed_residence_compatibility",
            "compatible_scope_labels", "compatible_working_time_regions",
            "confirmed_compatible", "employment_access_unspecified",
            "explicit_foreign_restriction", "incompatible_working_hours",
            "working_hours_unspecified",
        },
        "market_access_policy.remote",
    )
    if not isinstance(remote["residence_country"], str) or not remote["residence_country"].strip():
        raise Phase3ConfigurationError("remote residence_country must be a non-empty string")
    if not isinstance(remote["require_confirmed_residence_compatibility"], bool):
        raise Phase3ConfigurationError("require_confirmed_residence_compatibility must be boolean")
    _string_list(remote["compatible_scope_labels"], "remote scope label", REMOTE_SCOPE_LABELS)
    _string_list(
        remote["compatible_working_time_regions"],
        "working-time region",
        WORKING_TIME_REGIONS,
    )
    for field in (
        "confirmed_compatible", "employment_access_unspecified",
        "explicit_foreign_restriction", "incompatible_working_hours",
        "working_hours_unspecified",
    ):
        if remote[field] not in MARKET_SCOPE_STATUSES:
            raise Phase3ConfigurationError(f"invalid remote status: {field}={remote[field]!r}")

    relocation = _mapping(policy["relocation"], "market_access_policy.relocation")
    _exact_keys(relocation, {"mode", "normal_shortlist"}, "market_access_policy.relocation")
    if relocation["mode"] not in RELOCATION_MODES:
        raise Phase3ConfigurationError(f"invalid relocation mode: {relocation['mode']!r}")
    if not isinstance(relocation["normal_shortlist"], bool):
        raise Phase3ConfigurationError("relocation.normal_shortlist must be boolean")

    work_access = _mapping(policy["work_access"], "market_access_policy.work_access")
    if not work_access:
        raise Phase3ConfigurationError("market_access_policy.work_access cannot be empty")
    for jurisdiction, status in work_access.items():
        if not isinstance(jurisdiction, str) or not jurisdiction.strip():
            raise Phase3ConfigurationError("work-access jurisdictions must be non-empty strings")
        if status not in WORK_ACCESS_STATUSES:
            raise Phase3ConfigurationError(f"invalid work-access status: {status!r}")

    languages = _mapping(policy["languages"], "market_access_policy.languages")
    if not languages:
        raise Phase3ConfigurationError("market_access_policy.languages cannot be empty")
    for language, details in languages.items():
        if not isinstance(language, str) or not language.strip():
            raise Phase3ConfigurationError("language names must be non-empty strings")
        details = _mapping(details, f"market_access_policy.languages.{language}")
        if not {"support"} <= set(details) <= {"support", "notes"}:
            raise Phase3ConfigurationError(
                f"language {language!r} requires support and permits notes"
            )
        if details["support"] not in LANGUAGE_SUPPORT_LEVELS:
            raise Phase3ConfigurationError(f"invalid language support: {details['support']!r}")
        if "notes" in details and (
            not isinstance(details["notes"], str) or not details["notes"].strip()
        ):
            raise Phase3ConfigurationError("language notes must be a non-empty string")

    uncertainty = _mapping(policy["uncertainty"], "market_access_policy.uncertainty")
    _exact_keys(
        uncertainty, {"terminal_recommendation_cap"},
        "market_access_policy.uncertainty",
    )
    if uncertainty["terminal_recommendation_cap"] != "REVIEW":
        raise Phase3ConfigurationError("uncertain market status must be capped at REVIEW")

    seniority = _mapping(policy["seniority_guard"], "market_access_policy.seniority_guard")
    _exact_keys(
        seniority, {"explicit_levels", "terminal_recommendation_cap"},
        "market_access_policy.seniority_guard",
    )
    _string_list(seniority["explicit_levels"], "seniority guard level", SENIORITY_GUARD_LEVELS)
    if seniority["terminal_recommendation_cap"] != "LOW_PRIORITY":
        raise Phase3ConfigurationError("seniority guard must be capped at LOW_PRIORITY")

    return MarketAccessPolicy(
        policy_version=version,
        onsite_hybrid=onsite,
        remote=remote,
        relocation=relocation,
        work_access=work_access,
        languages=languages,
        uncertainty=uncertainty,
        seniority_guard=seniority,
    )


def load_candidate_profile(path: str | Path, taxonomy: Taxonomy) -> CandidateProfile:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required = {
        "profile", "facts", "capabilities", "experience", "preferences",
        "market_access_policy", "hard_constraints", "strategic_goals",
        "scoring_preferences",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise Phase3ConfigurationError("candidate profile has an invalid top-level schema")
    _validate_references(raw, taxonomy)
    market_access = _validate_market_access_policy(raw["market_access_policy"])
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
        profile_id=metadata["profile_id"],
        version=int(metadata["version"]),
        created_at=str(metadata["created_at"]),
        facts=raw["facts"],
        capabilities=tuple(raw["capabilities"]),
        experience=raw["experience"],
        preferences=raw["preferences"],
        market_access_policy=market_access,
        hard_constraints=raw["hard_constraints"],
        strategic_goals=tuple(raw["strategic_goals"]),
        scoring_weights={key: float(value) for key, value in weights.items()},
        full_profile_fingerprint=digest(raw),
        semantic_profile_fingerprint=digest(semantic),
        scoring_preference_fingerprint=digest(raw["scoring_preferences"]),
        market_access_policy_fingerprint=digest(raw["market_access_policy"]),
    )
