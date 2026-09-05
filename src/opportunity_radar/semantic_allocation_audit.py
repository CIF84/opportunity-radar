from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.decision_preferences import (
    assess_decision_preferences,
    load_preference_effect_policy,
    load_preference_matching_rules,
)
from opportunity_radar.decision_recomposition import recompose_cached_decision
from opportunity_radar.eligibility import evaluate_eligibility
from opportunity_radar.features import extract_features
from opportunity_radar.live_validation import (
    _active_rows,
    _readonly_connection,
    _semantic_job,
    current_judgments,
    load_judgments,
    observed_luna_cost,
)
from opportunity_radar.market_routing import compose_market_routing
from opportunity_radar.market_status import (
    evaluate_current_candidate_market,
    load_market_normalization_rules,
)
from opportunity_radar.phase3_config import digest, load_candidate_profile, load_taxonomy
from opportunity_radar.phase4_replay import load_replay_config
from opportunity_radar.prospective_validation import (
    build_current_cluster_population,
    historical_reviewed_job_ids,
    load_prospective_protocol,
    mark_historical_overlap,
)
from opportunity_radar.seniority_guard import (
    evaluate_seniority_guard,
    load_seniority_guard_rules,
)


DEFAULT_CONFIG = Path("experiments/semantic_compute_allocation_v1.yaml")
EXPERIMENT_TYPE = "PRE_SEMANTIC_COMPUTE_ALLOCATION_AUDIT"
TRIAGE_STATES = {"SEMANTIC_PRIORITY", "SEMANTIC_OPTIONAL", "SEMANTIC_DEFER"}
EVIDENCE_INVENTORY = {
    "title": "DETAIL_NORMALIZED",
    "employer": "DETAIL_NORMALIZED",
    "location": "DETAIL_NORMALIZED",
    "work_mode": "DETAIL_NORMALIZED",
    "employment_type": "DETAIL_NORMALIZED",
    "department": "DETAIL_NORMALIZED",
    "description": "DETAIL_NORMALIZED",
    "date_posted": "DETAIL_NORMALIZED",
    "source_updated_at": "DETAIL_NORMALIZED",
    "market_status": "DETERMINISTIC_DERIVED",
    "hard_eligibility": "DETERMINISTIC_DERIVED",
    "junior_graduate_evidence": "DETERMINISTIC_DERIVED",
    "lexical_taxonomy_concepts": "DETERMINISTIC_DERIVED",
    "opportunity_cluster": "DETERMINISTIC_DERIVED",
    "candidate_market_policy": "CANDIDATE_CONFIGURATION",
    "candidate_preferences": "CANDIDATE_CONFIGURATION",
    "semantic_cache_status": "HISTORICAL_CACHE_ONLY",
    "semantic_dimensions": "SEMANTIC_ONLY",
    "composite_score": "SEMANTIC_ONLY",
    "recommendation": "SEMANTIC_ONLY",
}


class SemanticAllocationAuditError(ValueError):
    pass


@dataclass(frozen=True)
class AllocationAuditConfig:
    raw: dict[str, Any]
    fingerprint: str
    role_patterns: dict[str, tuple[re.Pattern[str], ...]]
    positive_concepts: frozenset[str]

    @property
    def experiment_id(self) -> str:
        return str(self.raw["experiment_id"])


@dataclass(frozen=True)
class PreSemanticTriage:
    state: str
    positive_concepts: tuple[str, ...]
    positive_title_concepts: tuple[str, ...]
    positive_description_concepts: tuple[str, ...]
    obvious_role_families: tuple[str, ...]
    matched_preference_concepts: tuple[str, ...]
    deterministic_feature_concepts: tuple[str, ...]
    sparse_description: bool
    junior_or_graduate: bool
    reasons: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "positive_concepts": list(self.positive_concepts),
            "positive_title_concepts": list(self.positive_title_concepts),
            "positive_description_concepts": list(self.positive_description_concepts),
            "obvious_role_families": list(self.obvious_role_families),
            "matched_preference_concepts": list(self.matched_preference_concepts),
            "deterministic_feature_concepts": list(self.deterministic_feature_concepts),
            "sparse_description": self.sparse_description,
            "junior_or_graduate": self.junior_or_graduate,
            "reasons": list(self.reasons),
        }


def _sha256(path: str | Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load_allocation_audit_config(
    path: str | Path = DEFAULT_CONFIG,
) -> AllocationAuditConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version", "experiment_id", "experiment_type",
        "prospective_protocol_path", "replay_config_path", "obvious_role_families",
        "positive_protection_concepts", "uncertainty", "exploration", "outputs",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise SemanticAllocationAuditError("semantic allocation audit has an invalid schema")
    if raw["schema_version"] != 1 or raw["experiment_type"] != EXPERIMENT_TYPE:
        raise SemanticAllocationAuditError("unsupported semantic allocation audit identity")
    taxonomy = load_taxonomy("config/taxonomy.yaml")
    positives = raw["positive_protection_concepts"]
    if not isinstance(positives, list) or not positives or len(positives) != len(set(positives)):
        raise SemanticAllocationAuditError("positive protection concepts must be unique")
    for concept_id in positives:
        taxonomy.require(concept_id, "semantic allocation positive concept")
    role_patterns: dict[str, tuple[re.Pattern[str], ...]] = {}
    if not isinstance(raw["obvious_role_families"], dict):
        raise SemanticAllocationAuditError("obvious role families must be a mapping")
    for family, patterns in raw["obvious_role_families"].items():
        if not isinstance(patterns, list) or not patterns:
            raise SemanticAllocationAuditError(f"{family} must define title patterns")
        try:
            role_patterns[str(family)] = tuple(re.compile(x, re.I) for x in patterns)
        except (re.error, TypeError) as exc:
            raise SemanticAllocationAuditError(f"invalid role-family pattern: {exc}") from exc
    sparse = raw["uncertainty"].get("sparse_description_characters")
    if not isinstance(sparse, int) or isinstance(sparse, bool) or sparse < 0:
        raise SemanticAllocationAuditError("sparse description threshold must be non-negative")
    exploration = raw["exploration"]
    if set(exploration) != {"seed", "optional_sample_rate", "defer_sample_rate"}:
        raise SemanticAllocationAuditError("invalid exploration configuration")
    for field in ("optional_sample_rate", "defer_sample_rate"):
        value = float(exploration[field])
        if not 0 <= value <= 1:
            raise SemanticAllocationAuditError(f"{field} must be in [0, 1]")
    if raw["outputs"] != {
        "root": "output/semantic_compute_allocation",
        "detailed": "PRIVATE_LOCAL",
        "aggregate": "REPOSITORY_SAFE",
    }:
        raise SemanticAllocationAuditError("invalid audit output policy")
    return AllocationAuditConfig(raw, digest(raw), role_patterns, frozenset(positives))


def classify_presemantic_evidence(
    job,
    profile,
    taxonomy,
    config: AllocationAuditConfig,
    preference_policy,
    preference_rules,
    seniority_rules,
) -> PreSemanticTriage:
    """Classify compute priority without accepting cache or semantic inputs."""
    title = job.title or ""
    families = tuple(sorted(
        family for family, patterns in config.role_patterns.items()
        if any(pattern.search(title) for pattern in patterns)
    ))
    features = extract_features(job, taxonomy)
    feature_concepts = tuple(sorted({item.concept_id for item in features}))
    preference = assess_decision_preferences(
        job, None, profile, None, preference_policy, preference_rules,
    )
    preference_concepts = tuple(sorted({
        item.concept_id for item in preference.matched_effects
    }))
    positive = tuple(sorted(
        (set(feature_concepts) | set(preference_concepts)) & config.positive_concepts
    ))
    title_concepts = {
        item.concept_id for item in features if item.source_field == "title"
    } | {
        item.concept_id for item in preference.matched_effects
        if item.evidence_source == "title"
    }
    positive_title = tuple(sorted(title_concepts & config.positive_concepts))
    positive_description = tuple(sorted(set(positive) - set(positive_title)))
    sparse = len((job.description or "").strip()) < int(
        config.raw["uncertainty"]["sparse_description_characters"]
    )
    junior = evaluate_seniority_guard(job, profile, seniority_rules).active
    if positive_title:
        state = "SEMANTIC_PRIORITY"
        reasons = ("POSITIVE_TITLE_TARGET_EVIDENCE",)
        if families:
            reasons += ("POSITIVE_OVERRIDES_OBVIOUS_ROLE_FAMILY",)
    elif families and not positive_description:
        state = "SEMANTIC_DEFER"
        reasons = ("OBVIOUS_ROLE_FAMILY_WITHOUT_POSITIVE_PROTECTION",)
    elif sparse:
        state = "SEMANTIC_PRIORITY"
        reasons = ("INSUFFICIENT_DESCRIPTION_EVIDENCE_ESCALATED",)
    else:
        state = "SEMANTIC_OPTIONAL"
        reasons = (
            "DESCRIPTION_ONLY_POSITIVE_EVIDENCE"
            if positive_description else "PLAUSIBILITY_UNRESOLVED_BY_CHEAP_EVIDENCE",
        )
    if junior:
        reasons += ("EXPLICIT_JUNIOR_OR_GRADUATE_PRIORITIZATION_EVIDENCE",)
    assert state in TRIAGE_STATES
    return PreSemanticTriage(
        state, positive, positive_title, positive_description,
        families, preference_concepts, feature_concepts,
        sparse, junior, reasons,
    )


def _stable_fraction(seed: str, identity: str) -> float:
    value = hashlib.sha256(f"{seed}:{identity}".encode()).digest()[:8]
    return int.from_bytes(value, "big") / float(2**64)


def _stage_retained(item: dict[str, Any], stage: str, config: AllocationAuditConfig) -> bool:
    if not item["normal_candidate"]:
        return False
    triage = item["presemantic_triage"]["state"]
    if stage in {"F0_CURRENT_ROUTED", "F1_DETERMINISTIC_COMPATIBLE"}:
        return True
    if stage == "F2_CONSERVATIVE_ROLE_DEFER":
        return triage != "SEMANTIC_DEFER"
    if stage == "F3_TITLE_PRIORITY_ONLY_SCENARIO":
        return triage == "SEMANTIC_PRIORITY"
    if stage == "F4_ANY_LEXICAL_POSITIVE_SCENARIO":
        return bool(item["presemantic_triage"]["positive_concepts"]) or item["presemantic_triage"]["sparse_description"]
    if stage == "F5_PRIORITY_WITH_EXPLORATION":
        if triage == "SEMANTIC_PRIORITY":
            return True
        field = "optional_sample_rate" if triage == "SEMANTIC_OPTIONAL" else "defer_sample_rate"
        return _stable_fraction(
            str(config.raw["exploration"]["seed"]), item["audit_identity"],
        ) < float(config.raw["exploration"][field])
    raise SemanticAllocationAuditError(f"unknown funnel stage: {stage}")


FUNNEL_STAGES = (
    "F0_CURRENT_ROUTED",
    "F1_DETERMINISTIC_COMPATIBLE",
    "F2_CONSERVATIVE_ROLE_DEFER",
    "F3_TITLE_PRIORITY_ONLY_SCENARIO",
    "F4_ANY_LEXICAL_POSITIVE_SCENARIO",
    "F5_PRIORITY_WITH_EXPLORATION",
)


def _historical_units(config: AllocationAuditConfig, context: dict[str, Any]) -> list[dict[str, Any]]:
    replay = load_replay_config(config.raw["replay_config_path"])
    batch = json.loads(Path(replay.baseline["batch_path"]).read_text(encoding="utf-8"))
    judgments = current_judgments(
        load_judgments(replay.baseline["judgments_path"]), batch["validation_batch_id"],
    )
    grouped: dict[int, str] = {}
    group_decisions: dict[str, str] = {}
    for group in replay.human_opportunities:
        label = str(group["label"])
        group_decisions[label] = str(group["human_decision"])
        for review in group["review_numbers"]:
            grouped[int(review)] = label
    rows: list[dict[str, Any]] = []
    connection = _readonly_connection(replay.baseline["database_path"])
    try:
        for item in batch["selected_jobs"]:
            observation = connection.execute(
                "SELECT normalized_snapshot FROM job_observations WHERE job_observation_id=?",
                (item["job_observation_id"],),
            ).fetchone()
            if observation is None:
                raise SemanticAllocationAuditError("historical observation is unavailable")
            job = _semantic_job(json.loads(observation["normalized_snapshot"]))
            market = evaluate_current_candidate_market(job, context["profile"], context["market_rules"])
            eligibility = evaluate_eligibility(job, context["profile"])
            routing = compose_market_routing(market.status, eligibility.status)
            triage = classify_presemantic_evidence(job, **context["triage_args"])
            review = int(item["review_number"])
            judgment = judgments[(batch["validation_batch_id"], item["job_instance_id"])]
            label = grouped.get(review, f"review-{review}")
            rows.append({
                "audit_identity": f"historical:{label}:{review}",
                "opportunity_label": label,
                "review_number": review,
                "human_decision": group_decisions.get(label, judgment["decision"]),
                "normal_candidate": routing.include_in_normal_shortlist,
                "presemantic_triage": triage.payload(),
            })
    finally:
        connection.close()
    units: dict[str, dict[str, Any]] = {}
    for row in rows:
        unit = units.setdefault(row["opportunity_label"], {
            "opportunity_label": row["opportunity_label"],
            "human_decision": row["human_decision"],
            "members": [],
        })
        if unit["human_decision"] != row["human_decision"]:
            raise SemanticAllocationAuditError("historical opportunity has conflicting intent")
        unit["members"].append(row)
    return list(units.values())


def _coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    fields = {
        "title": lambda x: bool(x.get("title")),
        "employer": lambda x: bool(x.get("company_id")),
        "raw_location": lambda x: any(y.get("raw") for y in x.get("locations", [])),
        "structured_geography": lambda x: any(
            y.get(field) for y in x.get("locations", []) for field in ("city", "region", "country")
        ),
        "work_mode": lambda x: x.get("work_mode") not in {None, "", "unspecified"},
        "employment_type": lambda x: bool(x.get("employment_type")),
        "department": lambda x: bool(x.get("department")),
        "normalized_description": lambda x: bool(x.get("description")),
        "source_updated_at": lambda x: bool(x.get("source_updated_at")),
        "date_posted": lambda x: bool(x.get("date_posted")),
        "deterministic_features": lambda x: bool(x["presemantic_triage"]["deterministic_feature_concepts"]),
        "lexical_preference_evidence": lambda x: bool(x["presemantic_triage"]["matched_preference_concepts"]),
        "positive_protection_evidence": lambda x: bool(x["presemantic_triage"]["positive_concepts"]),
        "positive_title_evidence": lambda x: bool(x["presemantic_triage"]["positive_title_concepts"]),
        "positive_description_only_evidence": lambda x: bool(x["presemantic_triage"]["positive_description_concepts"]),
        "explicit_role_family": lambda x: bool(x["presemantic_triage"]["obvious_role_families"]),
        "explicit_junior_graduate": lambda x: bool(x["presemantic_triage"]["junior_or_graduate"]),
        "deterministic_market_status": lambda x: x.get("market_status") in {"IN_SCOPE", "UNCERTAIN", "OUT_OF_SCOPE"},
        "hard_eligibility": lambda x: x.get("eligibility") in {"ELIGIBLE", "UNCERTAIN", "INELIGIBLE"},
        "multi_member_cluster": lambda x: int(x.get("member_count", 1)) > 1,
    }
    total = len(rows)
    result: dict[str, dict[str, float | int]] = {}
    for name, predicate in fields.items():
        count = sum(bool(predicate(row)) for row in rows)
        result[name] = {
            "available": count,
            "total": total,
            "coverage": round(count / total, 6) if total else 0.0,
        }
    return result


def _funnel_metrics(
    rows: list[dict[str, Any]], historical: list[dict[str, Any]],
    config: AllocationAuditConfig, cost_per_miss: float,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    baseline = len(rows)
    for stage in FUNNEL_STAGES:
        retained = [row for row in rows if _stage_retained(row, stage, config)]
        apply_units = [x for x in historical if x["human_decision"] == "APPLY"]
        dont_units = [x for x in historical if x["human_decision"] == "DONT_APPLY"]
        retained_apply = [
            unit for unit in apply_units
            if any(_stage_retained(member, stage, config) for member in unit["members"])
        ]
        retained_dont = [
            unit for unit in dont_units
            if any(_stage_retained(member, stage, config) for member in unit["members"])
        ]
        misses = sum(x["semantic_cache_status"] == "SEMANTIC_CACHE_MISS" for x in retained)
        employer = Counter(x["company_id"] for x in retained)
        result[stage] = {
            "starting_population": baseline,
            "retained_count": len(retained),
            "deferred_count": baseline - len(retained),
            "reduction_fraction": round((baseline - len(retained)) / baseline, 6) if baseline else 0,
            "historical_apply_retained": len(retained_apply),
            "historical_apply_total": len(apply_units),
            "historical_apply_recall": round(len(retained_apply) / len(apply_units), 6) if apply_units else None,
            "historical_dont_apply_retained": len(retained_dont),
            "historical_dont_apply_total": len(dont_units),
            "cache_hits_diagnostic_only": sum(
                x["semantic_cache_status"] == "COMPATIBLE_SEMANTIC_CACHE_HIT" for x in retained
            ),
            "projected_luna_calls": misses,
            "projected_cost_usd": round(misses * cost_per_miss, 8),
            "market_status_distribution": dict(sorted(Counter(x["market_status"] for x in retained).items())),
            "employer_count": len(employer),
            "largest_employer_count": max(employer.values(), default=0),
            "largest_employer_fraction": round(max(employer.values(), default=0) / len(retained), 6) if retained else 0,
            "historical_apply_false_negative_units": [
                unit["opportunity_label"] for unit in apply_units if unit not in retained_apply
            ],
        }
    return result


def _recomposition_audit(database: str | Path, population: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
    hits = [x for x in population if x["semantic_cache_status"] == "COMPATIBLE_SEMANTIC_CACHE_HIT"]
    connection = _readonly_connection(database)
    succeeded = 0
    try:
        for item in hits:
            row = connection.execute(
                "SELECT * FROM semantic_assessments WHERE semantic_assessment_id=?",
                (item["semantic_assessment_id"],),
            ).fetchone()
            if row is None:
                raise SemanticAllocationAuditError("compatible semantic row disappeared")
            before = hashlib.sha256(row["assessment_json"].encode()).hexdigest()
            job = _semantic_job({
                "company_name": item["company_name"], "title": item["title"],
                "description": item["description"], "locations": item["locations"],
                "work_mode": item["work_mode"], "employment_type": item["employment_type"],
                "department": item["department"],
            })
            market = evaluate_current_candidate_market(job, context["profile"], context["market_rules"])
            eligibility = evaluate_eligibility(job, context["profile"])
            identity = {
                "semantic_assessment_id": row["semantic_assessment_id"],
                "content_fingerprint": row["content_fingerprint"],
                "semantic_profile_fingerprint": row["semantic_profile_fingerprint"],
                "semantic_contract_version": row["semantic_contract_version"],
                "assessor_id": row["assessor_id"],
                "assessor_version": row["assessor_version"],
            }
            decision = recompose_cached_decision(
                job, context["profile"], json.loads(row["assessment_json"]), identity,
                market, eligibility, context["preference_policy"], context["preference_rules"],
                context["seniority_rules"],
            )
            if decision.semantic_identity != identity:
                raise SemanticAllocationAuditError("recomposition changed semantic identity")
            after = hashlib.sha256(row["assessment_json"].encode()).hexdigest()
            if before != after:
                raise SemanticAllocationAuditError("recomposition mutated semantic payload")
            succeeded += 1
    finally:
        connection.close()
    return {
        "compatible_cache_hits_audited": len(hits),
        "successfully_recomposed": succeeded,
        "semantic_identity_preserved": succeeded == len(hits),
        "semantic_payload_unchanged": succeeded == len(hits),
        "external_calls": 0,
        "persistence_writes": 0,
    }


def run_semantic_allocation_audit(
    config_path: str | Path = DEFAULT_CONFIG,
    database: str | Path = "output/opportunity_radar.sqlite3",
    output_root: str | Path | None = None,
    *,
    run_id: str | None = None,
    write_artifact: bool = True,
) -> dict[str, Any]:
    config = load_allocation_audit_config(config_path)
    protocol = load_prospective_protocol(config.raw["prospective_protocol_path"])
    taxonomy = load_taxonomy(protocol.raw["taxonomy_path"])
    profile = load_candidate_profile(protocol.raw["candidate_path"], taxonomy)
    market_rules = load_market_normalization_rules(protocol.raw["market_rules_path"])
    preference_policy = load_preference_effect_policy(protocol.raw["preference_effect_policy_path"])
    preference_rules = load_preference_matching_rules(taxonomy, protocol.raw["preference_matching_rules_path"])
    seniority_rules = load_seniority_guard_rules(protocol.raw["seniority_rules_path"])
    context = {
        "profile": profile, "market_rules": market_rules,
        "preference_policy": preference_policy, "preference_rules": preference_rules,
        "seniority_rules": seniority_rules,
    }
    context["triage_args"] = {
        "profile": profile, "taxonomy": taxonomy, "config": config,
        "preference_policy": preference_policy, "preference_rules": preference_rules,
        "seniority_rules": seniority_rules,
    }
    database_hash_before = _sha256(database)
    prospective_hash_before = _sha256(config.raw["prospective_protocol_path"])
    population, population_metadata = build_current_cluster_population(database, protocol)
    reviewed = historical_reviewed_job_ids(protocol.raw["historical_batch_path"])
    population, historical_exclusion = mark_historical_overlap(population, reviewed)
    active_snapshots: dict[int, dict[str, Any]] = {}
    with _readonly_connection(database) as connection:
        for row in _active_rows(connection):
            active_snapshots[int(row["job_instance_id"])] = row["snapshot"]
    audit_rows: list[dict[str, Any]] = []
    for item in population:
        if item["historical_reviewed_overlap"]:
            continue
        job = _semantic_job({
            "company_name": item["company_name"], "title": item["title"],
            "description": item["description"], "locations": item["locations"],
            "work_mode": item["work_mode"], "employment_type": item["employment_type"],
            "department": item["department"],
        })
        triage = classify_presemantic_evidence(job, **context["triage_args"])
        snapshot = active_snapshots.get(int(item["preferred_variant_job_instance_id"]), {})
        audit_rows.append({
            **item,
            "audit_identity": item["cluster_id"],
            "source_updated_at": snapshot.get("source_updated_at"),
            "date_posted": snapshot.get("date_posted"),
            "presemantic_triage": triage.payload(),
        })
    routed = [item for item in audit_rows if item["normal_candidate"]]
    historical = _historical_units(config, context)
    cost = observed_luna_cost(protocol.raw["roi_results_path"])
    funnels = _funnel_metrics(
        routed, historical, config, cost["estimated_cost_per_cache_miss_usd"],
    )
    recomposition = _recomposition_audit(database, audit_rows, context)
    database_hash_after = _sha256(database)
    prospective_hash_after = _sha256(config.raw["prospective_protocol_path"])
    if database_hash_before != database_hash_after:
        raise SemanticAllocationAuditError("audit mutated the operational database")
    if prospective_hash_before != prospective_hash_after:
        raise SemanticAllocationAuditError("audit mutated the frozen prospective protocol")
    run_id = run_id or (
        "semantic-allocation-audit-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    )
    triage_counts = dict(sorted(Counter(
        item["presemantic_triage"]["state"] for item in routed
    ).items()))
    thresholds = {}
    for threshold in (1000, 500, 250, 100):
        qualifying = [
            name for name, value in funnels.items()
            if value["projected_luna_calls"] <= threshold
            and value["historical_apply_recall"] == 1.0
        ]
        thresholds[str(threshold)] = {
            "historical_recall_safe_scenario_found": bool(qualifying),
            "qualifying_scenarios": qualifying,
        }
    result = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment_id": config.experiment_id,
        "experiment_type": EXPERIMENT_TYPE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "population_metadata": population_metadata,
        "historical_exclusion": historical_exclusion,
        "routed_population": routed,
        "evidence_coverage": _coverage(routed),
        "evidence_inventory": EVIDENCE_INVENTORY,
        "triage_distribution": triage_counts,
        "funnels": funnels,
        "historical_units": historical,
        "target_scenarios": thresholds,
        "recomposition": recomposition,
        "model_cost": {
            "model": "gpt-5.6-luna", "reasoning_effort": "low",
            "semantic_contract": "phase3-semantic-v1",
            "estimated_cost_per_miss_usd": cost["estimated_cost_per_cache_miss_usd"],
        },
        "integrity": {
            "database_sha256_before": database_hash_before,
            "database_sha256_after": database_hash_after,
            "database_unchanged": True,
            "prospective_protocol_sha256_before": prospective_hash_before,
            "prospective_protocol_sha256_after": prospective_hash_after,
            "prospective_protocol_unchanged": True,
            "external_semantic_calls": 0,
            "live_source_calls": 0,
            "prospective_batches_created": 0,
            "judgments_created": 0,
        },
        "configuration": {
            "audit_fingerprint": config.fingerprint,
            "prospective_protocol_fingerprint": protocol.fingerprint,
            "candidate_full_profile_fingerprint": profile.full_profile_fingerprint,
            "candidate_semantic_profile_fingerprint": profile.semantic_profile_fingerprint,
            "market_policy_fingerprint": profile.market_access_policy_fingerprint,
            "decision_preference_fingerprint": profile.decision_preference_fingerprint,
        },
    }
    if write_artifact:
        root = Path(output_root or config.raw["outputs"]["root"])
        directory = root / run_id
        directory.mkdir(parents=True, exist_ok=False)
        detailed_path = directory / "audit.json"
        detailed_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        safe_funnels = {
            name: {k: v for k, v in value.items() if k != "historical_apply_false_negative_units"}
            for name, value in funnels.items()
        }
        aggregate = {
            "schema_version": 1,
            "run_id": run_id,
            "experiment_id": config.experiment_id,
            "experiment_type": EXPERIMENT_TYPE,
            "created_at": result["created_at"],
            "baseline": {
                "active_clusters": population_metadata["cluster_count"],
                "post_historical_routed_clusters": len(routed),
                "historical_exclusion": historical_exclusion,
                "cache_status_counts_diagnostic_only": dict(sorted(Counter(
                    x["semantic_cache_status"] for x in routed
                ).items())),
            },
            "evidence_coverage": result["evidence_coverage"],
            "evidence_inventory": EVIDENCE_INVENTORY,
            "triage_distribution": triage_counts,
            "funnels": safe_funnels,
            "target_scenarios": thresholds,
            "recomposition": recomposition,
            "model_cost": result["model_cost"],
            "configuration": result["configuration"],
            "integrity": result["integrity"],
            "privacy": {
                "detailed_artifact": "PRIVATE_LOCAL",
                "detailed_sha256": _sha256(detailed_path),
                "aggregate_artifact": "REPOSITORY_SAFE",
            },
            "limitations": [
                "Historical judgments are a small biased safety corpus, not training data.",
                "No compute-allocation policy is promoted by this audit.",
                "Priority-only and exploration scenarios change the scientific population and require a separately frozen prospective protocol.",
                "Cache status is reported only as execution-budget evidence and is not an input to triage.",
            ],
            "conclusions": [
                "The current deterministic route is already conservative, so deterministic incompatibility removes no additional routed clusters.",
                "Conservative obvious-role-family deferral preserves all five historical human-APPLY opportunity units but reduces projected calls by less than one percent.",
                "Title-positive prioritization reaches a sub-500-call scenario but retains only three of five historical human-APPLY opportunity units.",
                "Description-level positive language is too common to provide useful reduction and still misses one historical human-APPLY opportunity.",
                "No audited interpretable funnel reaches 1000, 500, 250, or 100 calls while preserving all historical human-APPLY opportunities.",
                "A bounded cache-blind human compute-worthiness labeling experiment is warranted before promoting a protocol-v2 allocation funnel.",
            ],
            "recommendation": "FURTHER_BOUNDED_EXPERIMENT_BEFORE_PROTOCOL_V2_OR_FULL_COMPLETION",
        }
        aggregate_path = directory / "aggregate_summary.json"
        aggregate_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n")
        result["artifact_paths"] = {
            "private_detailed": str(detailed_path),
            "repository_safe_aggregate": str(aggregate_path),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Phase 4 semantic compute-allocation audit")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--database", default="output/opportunity_radar.sqlite3")
    parser.add_argument("--output-root")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run_semantic_allocation_audit(
        args.config, args.database, args.output_root,
        run_id=args.run_id, write_artifact=not args.dry_run,
    )
    print(json.dumps({
        "run_id": result["run_id"],
        "baseline": len(result["routed_population"]),
        "triage_distribution": result["triage_distribution"],
        "funnels": {
            key: {
                "retained": value["retained_count"],
                "historical_apply_recall": value["historical_apply_recall"],
                "projected_luna_calls": value["projected_luna_calls"],
                "projected_cost_usd": value["projected_cost_usd"],
            }
            for key, value in result["funnels"].items()
        },
        "external_calls": 0,
        "artifact_paths": result.get("artifact_paths"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
