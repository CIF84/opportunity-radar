from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.decision_preferences import (
    PreferenceMatchingRules,
    assess_decision_preferences,
    load_preference_effect_policy,
    load_preference_matching_rules,
)
from opportunity_radar.live_validation import _clustered_assessed_pool
from opportunity_radar.market_routing import compose_market_routing
from opportunity_radar.market_status import (
    CurrentCandidateMarketStatus,
    load_market_normalization_rules,
)
from opportunity_radar.phase3_config import digest, load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import (
    CandidateProfile,
    DecisionPreference,
    DecisionPreferences,
    EligibilityStatus,
    SemanticJobInput,
)
from opportunity_radar.phase4_replay import (
    _clusters,
    _load_rows,
    _posting_replay,
    load_replay_config,
)
from opportunity_radar.scoring import derive_recommendation
from opportunity_radar.semantic_worthiness_validation import (
    _current_append_only,
    effective_selected_items,
    load_jsonl,
)
from opportunity_radar.seniority_guard import (
    apply_seniority_guard,
    evaluate_seniority_guard,
    load_seniority_guard_rules,
)


DEFAULT_CONFIG = Path("experiments/candidate_direction_promotion_v1.yaml")
EXPERIMENT_TYPE = "CANDIDATE_DIRECTION_PROMOTION_AUDIT"


class CandidateDirectionAuditError(ValueError):
    pass


@dataclass(frozen=True)
class CandidateDirectionAuditConfig:
    raw: dict[str, Any]
    fingerprint: str

    @property
    def experiment_id(self) -> str:
        return str(self.raw["experiment_id"])


def _sha256(path: str | Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], check=True, capture_output=True, text=True,
    ).stdout.strip())
    return {"commit": commit, "dirty": dirty}


def load_candidate_direction_audit_config(
    path: str | Path = DEFAULT_CONFIG,
) -> CandidateDirectionAuditConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required = {
        "schema_version", "experiment_id", "experiment_type", "specification",
        "inputs", "baseline_candidate", "frozen_semantic", "baseline_matching_rules",
        "proposed_candidate", "concept_audit", "promotion_gates", "privacy", "outputs",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise CandidateDirectionAuditError("candidate-direction audit has an invalid schema")
    if raw["schema_version"] != 1 or raw["experiment_type"] != EXPERIMENT_TYPE:
        raise CandidateDirectionAuditError("unsupported candidate-direction audit identity")
    inputs = raw["inputs"]
    expected_inputs = {
        "candidate_path", "portability_candidate_path", "taxonomy_path",
        "matching_rules_path", "effect_policy_path", "market_rules_path",
        "seniority_rules_path", "database_path", "worthiness_manifest_path",
        "worthiness_judgments_path", "worthiness_replacements_path",
        "retrospective_config_path",
    }
    if not isinstance(inputs, dict) or set(inputs) != expected_inputs:
        raise CandidateDirectionAuditError("candidate-direction inputs have an invalid schema")
    # The operational database and detailed human evidence are intentionally
    # private/local, so schema loading must remain possible in a fresh clone.
    public_input_keys = {
        "candidate_path", "portability_candidate_path", "taxonomy_path",
        "matching_rules_path", "effect_policy_path", "market_rules_path",
        "seniority_rules_path", "retrospective_config_path",
    }
    for key in public_input_keys:
        if not Path(inputs[key]).exists():
            raise CandidateDirectionAuditError(
                f"configured repository input does not exist: {inputs[key]}"
            )
    if raw["privacy"] != {
        "detailed_artifact": "PRIVATE_LOCAL",
        "aggregate_artifact": "REPOSITORY_SAFE",
        "raw_human_notes": "PRIVATE_LOCAL_APPEND_ONLY",
    }:
        raise CandidateDirectionAuditError("invalid candidate-direction privacy boundary")
    verdicts = {
        "ALREADY_REPRESENTED_SUFFICIENTLY", "PROMOTE_STRONG_POSITIVE",
        "PROMOTE_POSITIVE", "PROMOTE_NEGATIVE", "KEEP_CONTEXTUAL_ONLY",
        "KEEP_AS_CONVICTION_ONLY", "INSUFFICIENT_EVIDENCE",
        "REJECT_CAPABILITY_CONFUSION",
    }
    concepts = raw["concept_audit"]
    if not isinstance(concepts, list) or not concepts:
        raise CandidateDirectionAuditError("concept_audit must be a non-empty list")
    concept_ids = [item.get("concept_id") for item in concepts if isinstance(item, dict)]
    if len(concept_ids) != len(concepts) or len(set(concept_ids)) != len(concept_ids):
        raise CandidateDirectionAuditError("concept_audit IDs must be unique")
    if any(item.get("verdict") not in verdicts for item in concepts):
        raise CandidateDirectionAuditError("concept_audit contains an invalid verdict")
    return CandidateDirectionAuditConfig(raw, digest(raw))


def _decision_preferences(raw: dict[str, Any]) -> DecisionPreferences:
    return DecisionPreferences(
        schema_version=int(raw["schema_version"]),
        preference_version=int(raw["preference_version"]),
        entries=tuple(DecisionPreference(
            concept_id=str(item["concept_id"]),
            source_type=str(item["source_type"]),
            stance=str(item["stance"]),
            rationale=item.get("rationale"),
        ) for item in raw["entries"]),
    )


def _baseline_profile(
    promoted: CandidateProfile, config: CandidateDirectionAuditConfig,
) -> CandidateProfile:
    raw = config.raw["baseline_candidate"]
    decision = _decision_preferences(raw["decision_preferences"])
    baseline = replace(
        promoted,
        version=int(raw["profile_version"]),
        created_at=str(raw["created_at"]),
        decision_preferences=decision,
        full_profile_fingerprint=str(raw["full_profile_fingerprint"]),
        decision_preference_fingerprint=str(raw["decision_preference_fingerprint"]),
    )
    expected = {
        "semantic_profile_fingerprint": promoted.semantic_profile_fingerprint,
        "scoring_preference_fingerprint": promoted.scoring_preference_fingerprint,
        "market_access_policy_fingerprint": promoted.market_access_policy_fingerprint,
    }
    for key, actual in expected.items():
        if raw[key] != actual:
            raise CandidateDirectionAuditError(f"baseline {key} does not match promoted profile")
    if digest(decision.payload()) != raw["decision_preference_fingerprint"]:
        raise CandidateDirectionAuditError("baseline decision-preference fingerprint is invalid")
    return baseline


def _baseline_rules(
    promoted: PreferenceMatchingRules, config: CandidateDirectionAuditConfig,
) -> PreferenceMatchingRules:
    promoted_ids = {
        item["concept_id"] for item in config.raw["proposed_candidate"]["promoted_entries"]
    }
    raw = config.raw["baseline_matching_rules"]
    rules = replace(
        promoted,
        version=int(raw["version"]),
        concepts={key: value for key, value in promoted.concepts.items() if key not in promoted_ids},
        fingerprint=str(raw["fingerprint"]),
    )
    return rules


def _semantic_job(item: dict[str, Any]) -> SemanticJobInput:
    return SemanticJobInput(
        company_name=str(item.get("company_name", "Unknown")),
        title=item.get("title"),
        description=str(item.get("description_excerpt") or item.get("description") or ""),
        locations=tuple(item.get("locations", [])),
        work_mode=str(item.get("work_mode", "unspecified")),
        employment_type=item.get("employment_type"),
        department=item.get("department"),
    )


def _promoted_effects(value: Any, promoted_ids: set[str]) -> list[dict[str, Any]]:
    return [
        asdict(item) for item in value.matched_effects if item.concept_id in promoted_ids
    ]


def _worthiness_replay(
    config: CandidateDirectionAuditConfig,
    baseline: CandidateProfile,
    promoted: CandidateProfile,
    policy: Any,
    baseline_rules: PreferenceMatchingRules,
    promoted_rules: PreferenceMatchingRules,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inputs = config.raw["inputs"]
    manifest = json.loads(Path(inputs["worthiness_manifest_path"]).read_text(encoding="utf-8"))
    selected = effective_selected_items(
        manifest, load_jsonl(inputs["worthiness_replacements_path"]),
    )
    judgments = _current_append_only(
        load_jsonl(inputs["worthiness_judgments_path"]),
        manifest["preparation_id"], "cluster_id",
    )
    promoted_ids = {
        item["concept_id"] for item in config.raw["proposed_candidate"]["promoted_entries"]
    }
    detail: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    effect_counts: Counter[str] = Counter()
    for item in selected:
        judgment = judgments.get(item["cluster_id"])
        if judgment is None:
            raise CandidateDirectionAuditError("frozen worthiness sample is not fully reviewed")
        job = _semantic_job(item)
        before = assess_decision_preferences(job, None, baseline, None, policy, baseline_rules)
        after = assess_decision_preferences(job, None, promoted, None, policy, promoted_rules)
        effects = _promoted_effects(after, promoted_ids)
        if effects:
            label_counts[judgment["label"]] += 1
            effect_counts.update(value["concept_id"] for value in effects)
        detail.append({
            "review_number": item["review_number"],
            "cluster_id": item["cluster_id"],
            "human_label": judgment["label"],
            "promoted_effects": effects,
            "existing_effect_count": len(before.matched_effects),
            "effect_overlap": bool(effects and before.matched_effects),
        })
    matched = [item for item in detail if item["promoted_effects"]]
    return {
        "sample_size": len(detail),
        "reviewed": len(judgments),
        "promoted_effect_matches": len(matched),
        "promoted_effects_by_concept": dict(sorted(effect_counts.items())),
        "matched_human_labels": dict(sorted(label_counts.items())),
        "known_worth_demotions": sum(
            item["human_label"] == "WORTH_DEEP_ASSESSMENT" for item in matched
        ),
        "overlap_with_existing_effects": sum(item["effect_overlap"] for item in matched),
        "limitations": "Frozen blind evidence contains excerpts rather than guaranteed full descriptions; title-only promoted matching is fully observable.",
    }, detail


def _final_recommendation(
    job: SemanticJobInput,
    profile: CandidateProfile,
    row: dict[str, Any],
    adjusted_score: float | None,
    seniority_rules: Any,
) -> str | None:
    eligibility = EligibilityStatus(row["eligibility"])
    base = derive_recommendation(eligibility.value, adjusted_score)
    routed = compose_market_routing(
        CurrentCandidateMarketStatus(row["market_status"]), eligibility, base,
    )
    guard = evaluate_seniority_guard(job, profile, seniority_rules)
    return apply_seniority_guard(routed.recommendation, guard).recommendation.value \
        if routed.recommendation else None


def _rank_map(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    ordered = sorted(
        rows,
        key=lambda row: (
            -(row[key] if row[key] is not None else -1), str(row["cluster_id"]),
        ),
    )
    return {str(row["cluster_id"]): index for index, row in enumerate(ordered, 1)}


def _cached_population_replay(
    config: CandidateDirectionAuditConfig,
    baseline: CandidateProfile,
    promoted: CandidateProfile,
    taxonomy: Any,
    policy: Any,
    baseline_rules: PreferenceMatchingRules,
    promoted_rules: PreferenceMatchingRules,
    seniority_rules: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inputs = config.raw["inputs"]
    semantic = config.raw["frozen_semantic"]
    market_rules = load_market_normalization_rules(inputs["market_rules_path"])
    rows, _ = _clustered_assessed_pool(
        inputs["database_path"], promoted, semantic["assessor_version"],
        market_rules, taxonomy, inputs["effect_policy_path"], inputs["matching_rules_path"],
        inputs["seniority_rules_path"],
    )
    promoted_ids = {
        item["concept_id"] for item in config.raw["proposed_candidate"]["promoted_entries"]
    }
    observation_ids = [row["job_observation_id"] for row in rows]
    snapshots: dict[int, dict[str, Any]] = {}
    if observation_ids:
        uri = f"file:{Path(inputs['database_path']).resolve()}?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.execute("PRAGMA query_only = ON")
            placeholders = ",".join("?" for _ in observation_ids)
            snapshots = {
                int(row[0]): json.loads(row[1])
                for row in connection.execute(
                    f"SELECT job_observation_id,normalized_snapshot FROM job_observations "
                    f"WHERE job_observation_id IN ({placeholders})",
                    observation_ids,
                )
            }
    detail: list[dict[str, Any]] = []
    for row in rows:
        # The pool deliberately omits descriptions. Retrieve only the immutable
        # latest normalized snapshot from local SQLite for deterministic matching.
        snapshot = snapshots[int(row["job_observation_id"])]
        job = SemanticJobInput(
            snapshot["company_name"], snapshot.get("title"), snapshot.get("description") or "",
            tuple(snapshot.get("locations", [])), snapshot.get("work_mode", "unspecified"),
            snapshot.get("employment_type"), snapshot.get("department"),
        )
        before = assess_decision_preferences(
            job, row.get("semantic"), baseline, row["base_composite_score"],
            policy, baseline_rules,
        )
        after = assess_decision_preferences(
            job, row.get("semantic"), promoted, row["base_composite_score"],
            policy, promoted_rules,
        )
        detail.append({
            "cluster_id": row["cluster_id"],
            "company_id": row["company_id"],
            "semantic_assessment_id": row["semantic_assessment_id"],
            "base_score": row["base_composite_score"],
            "before_score": before.decision_adjusted_score,
            "after_score": after.decision_adjusted_score,
            "before_recommendation": _final_recommendation(
                job, baseline, row, before.decision_adjusted_score, seniority_rules,
            ),
            "after_recommendation": _final_recommendation(
                job, promoted, row, after.decision_adjusted_score, seniority_rules,
            ),
            "promoted_effects": _promoted_effects(after, promoted_ids),
            "before_raw_effect": before.raw_total_effect,
            "after_raw_effect": after.raw_total_effect,
            "before_bounded_effect": before.bounded_total_effect,
            "after_bounded_effect": after.bounded_total_effect,
            "existing_effect_overlap": bool(
                _promoted_effects(after, promoted_ids) and before.matched_effects
            ),
        })
    before_ranks = _rank_map(detail, "before_score")
    after_ranks = _rank_map(detail, "after_score")
    for row in detail:
        row["before_rank"] = before_ranks[row["cluster_id"]]
        row["after_rank"] = after_ranks[row["cluster_id"]]
    matched = [row for row in detail if row["promoted_effects"]]
    return {
        "compatible_cached_opportunities": len(detail),
        "promoted_effect_matches": len(matched),
        "score_changes": sum(row["before_score"] != row["after_score"] for row in detail),
        "recommendation_changes": sum(
            row["before_recommendation"] != row["after_recommendation"] for row in detail
        ),
        "rank_changes": sum(row["before_rank"] != row["after_rank"] for row in detail),
        "effect_clipping_before": sum(
            row["before_raw_effect"] != row["before_bounded_effect"] for row in detail
        ),
        "effect_clipping_after": sum(
            row["after_raw_effect"] != row["after_bounded_effect"] for row in detail
        ),
        "overlap_with_existing_effects": sum(row["existing_effect_overlap"] for row in matched),
        "semantic_reassessments": 0,
        "semantic_assessment_ids_preserved": len({row["semantic_assessment_id"] for row in detail}),
    }, detail


def _retrospective_replay(
    config: CandidateDirectionAuditConfig,
    baseline: CandidateProfile,
    promoted: CandidateProfile,
    taxonomy: Any,
    policy: Any,
    baseline_rules: PreferenceMatchingRules,
    promoted_rules: PreferenceMatchingRules,
    seniority_rules: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inputs = config.raw["inputs"]
    replay_config = load_replay_config(inputs["retrospective_config_path"])
    market_rules = load_market_normalization_rules(inputs["market_rules_path"])
    _, rows, _ = _load_rows(replay_config, baseline)
    before = _posting_replay(
        rows, baseline, taxonomy, market_rules, policy, baseline_rules, seniority_rules,
    )
    after = _posting_replay(
        rows, promoted, taxonomy, market_rules, policy, promoted_rules, seniority_rules,
    )
    before_clusters, _ = _clusters(before, baseline, replay_config)
    after_clusters, _ = _clusters(after, promoted, replay_config)
    before_by_review = {row["review_number"]: row for row in before}
    detail: list[dict[str, Any]] = []
    for row in after:
        prior = before_by_review[row["review_number"]]
        detail.append({
            "review_number": row["review_number"],
            "human_decision": row["human"]["decision"],
            "before_score": prior["decision_adjusted_score"],
            "after_score": row["decision_adjusted_score"],
            "before_recommendation": prior["final_recommendation"],
            "after_recommendation": row["final_recommendation"],
            "promoted_effects": [
                effect for effect in row["preference_assessment"]["matched_effects"]
                if effect["concept_id"] in {
                    item["concept_id"]
                    for item in config.raw["proposed_candidate"]["promoted_entries"]
                }
            ],
        })
    known_positive_demotions = sum(
        row["human_decision"] == "APPLY"
        and row["after_recommendation"] not in {"APPLY", "REVIEW"}
        and row["before_recommendation"] in {"APPLY", "REVIEW"}
        for row in detail
    )
    return {
        "postings": len(detail),
        "opportunities_before": len(before_clusters),
        "opportunities_after": len(after_clusters),
        "promoted_effect_matches": sum(bool(row["promoted_effects"]) for row in detail),
        "score_changes": sum(row["before_score"] != row["after_score"] for row in detail),
        "recommendation_changes": sum(
            row["before_recommendation"] != row["after_recommendation"] for row in detail
        ),
        "known_human_apply_demotions": known_positive_demotions,
        "cluster_membership_changed": sorted(
            row["cluster_fingerprint"] for row in before_clusters
        ) != sorted(row["cluster_fingerprint"] for row in after_clusters),
        "semantic_reassessments": 0,
    }, detail


def _promotion_gate_results(
    config: CandidateDirectionAuditConfig,
    baseline: CandidateProfile,
    promoted: CandidateProfile,
    worthiness: dict[str, Any],
    cached: dict[str, Any],
    retrospective: dict[str, Any],
    rules: PreferenceMatchingRules,
) -> list[dict[str, Any]]:
    proposed = config.raw["proposed_candidate"]
    gates = config.raw["promotion_gates"]
    promoted_ids = {item["concept_id"] for item in proposed["promoted_entries"]}
    narrow = all(
        bool(rules.concepts[concept]["title_match_any"])
        and not rules.concepts[concept]["match_any"]
        and not rules.concepts[concept]["description_match_any"]
        for concept in promoted_ids
    )
    results = [
        ("repeated_explicit_evidence", all(
            int(item["evidence_count"]) >= 2 for item in proposed["promoted_entries"]
        )),
        ("narrow_matching", narrow),
        ("known_positive_evidence_preserved", (
            worthiness["known_worth_demotions"]
            + retrospective["known_human_apply_demotions"]
        ) <= int(gates["known_positive_demotion_maximum"])),
        ("semantic_profile_unchanged", baseline.semantic_profile_fingerprint == promoted.semantic_profile_fingerprint),
        ("scoring_preferences_unchanged", baseline.scoring_preference_fingerprint == promoted.scoring_preference_fingerprint),
        ("market_policy_unchanged", baseline.market_access_policy_fingerprint == promoted.market_access_policy_fingerprint),
        ("decision_preference_changed", baseline.decision_preference_fingerprint != promoted.decision_preference_fingerprint),
        ("full_profile_changed", baseline.full_profile_fingerprint != promoted.full_profile_fingerprint),
        ("zero_semantic_reassessments", (
            cached["semantic_reassessments"] + retrospective["semantic_reassessments"]
        ) <= int(gates["semantic_reassessments_maximum"])),
        ("clustering_unchanged", not retrospective["cluster_membership_changed"]),
    ]
    return [
        {"gate": name, "status": "PASS" if passed else "FAIL"}
        for name, passed in results
    ]


def _enriched_concept_audit(
    config: CandidateDirectionAuditConfig,
    profile: CandidateProfile,
    taxonomy: Any,
    rules: PreferenceMatchingRules,
) -> list[dict[str, Any]]:
    decision_ids = {item.concept_id for item in profile.decision_preferences.entries}
    capability_ids = {item["capability_id"] for item in profile.capabilities}
    role_ids = {
        item["characteristic_id"]
        for item in profile.preferences.get("role_characteristics", [])
    }
    goal_ids = {item["goal_id"] for item in profile.strategic_goals}
    result = []
    for item in config.raw["concept_audit"]:
        concept_id = item["concept_id"]
        existing = []
        if concept_id in decision_ids:
            existing.append("DECISION_PREFERENCE")
        if concept_id in capability_ids:
            existing.append("CAPABILITY")
        if concept_id in role_ids:
            existing.append("SEMANTIC_ROLE_CHARACTERISTIC")
        if concept_id in goal_ids:
            existing.append("STRATEGIC_GOAL")
        promoted = item["verdict"].startswith("PROMOTE_")
        result.append({
            **item,
            "existing_representation": existing,
            "proposed_source_type": item.get("proposed_source_type"),
            "proposed_stance": item.get("proposed_stance"),
            "taxonomy_supported": concept_id in taxonomy.concepts,
            "matching_supported": concept_id in rules.concepts,
            "would_require_taxonomy_or_matching_extension": (
                concept_id not in taxonomy.concepts or concept_id not in rules.concepts
            ),
            "fingerprint_cache_implication": (
                "DECISION_MATCHING_AND_FULL_PROFILE_IDENTITIES_CHANGE; SEMANTIC_CACHE_REUSED"
                if promoted else "NO_RUNTIME_IDENTITY_CHANGE"
            ),
        })
    return result


def build_sanitized_summary(result: dict[str, Any], detailed_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "evidence_class": "SANITIZED_AGGREGATE_EXPERIMENT_RESULT",
        "experiment_id": result["experiment_id"],
        "run_id": result["run_id"],
        "created_at": result["created_at"],
        "experiment_type": result["experiment_type"],
        "concept_audit": result["concept_audit"],
        "counterfactual": result["counterfactual"],
        "fingerprints": result["fingerprints"],
        "promotion_gates": result["promotion_gates"],
        "promotion_decision": result["promotion_decision"],
        "stretch_envelope": result["stretch_envelope"],
        "integrity": result["integrity"],
        "privacy": {
            "classification": "REPOSITORY_SAFE_AGGREGATE",
            "private_detailed_artifact_sha256": detailed_sha256,
            "excluded_detail": "RAW_HUMAN_NOTES_TITLES_URLS_CLUSTER_IDENTITIES_AND_PER_OPPORTUNITY_EFFECTS",
        },
        "limitations": result["limitations"],
    }


def run_candidate_direction_audit(
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path | None = None,
    *,
    run_id: str | None = None,
    write_artifact: bool = True,
) -> dict[str, Any]:
    config = load_candidate_direction_audit_config(config_path)
    raw, inputs = config.raw, config.raw["inputs"]
    for key in (
        "database_path", "worthiness_manifest_path", "worthiness_judgments_path",
        "worthiness_replacements_path",
    ):
        if not Path(inputs[key]).exists():
            raise CandidateDirectionAuditError(
                f"required private/local audit input does not exist: {inputs[key]}"
            )
    database_hash_before = _sha256(inputs["database_path"])
    taxonomy = load_taxonomy(inputs["taxonomy_path"])
    promoted = load_candidate_profile(inputs["candidate_path"], taxonomy)
    portability = load_candidate_profile(inputs["portability_candidate_path"], taxonomy)
    baseline = _baseline_profile(promoted, config)
    expected = raw["proposed_candidate"]
    if promoted.version != expected["profile_version"]:
        raise CandidateDirectionAuditError("promoted candidate version does not match audit")
    if promoted.decision_preferences.preference_version != expected["preference_version"]:
        raise CandidateDirectionAuditError("promoted preference version does not match audit")
    for key in ("full_profile_fingerprint", "decision_preference_fingerprint"):
        if getattr(promoted, key) != expected[key]:
            raise CandidateDirectionAuditError(f"promoted {key} does not match audit")
    policy = load_preference_effect_policy(inputs["effect_policy_path"])
    promoted_rules = load_preference_matching_rules(taxonomy, inputs["matching_rules_path"])
    baseline_rules = _baseline_rules(promoted_rules, config)
    raw_rules = yaml.safe_load(Path(inputs["matching_rules_path"]).read_text(encoding="utf-8"))
    raw_rules["version"] = config.raw["baseline_matching_rules"]["version"]
    for item in expected["promoted_entries"]:
        raw_rules["concepts"].pop(item["concept_id"], None)
    if digest(raw_rules) != baseline_rules.fingerprint:
        raise CandidateDirectionAuditError("baseline matching-rules fingerprint is invalid")
    seniority_rules = load_seniority_guard_rules(inputs["seniority_rules_path"])

    worthiness, worthiness_detail = _worthiness_replay(
        config, baseline, promoted, policy, baseline_rules, promoted_rules,
    )
    cached, cached_detail = _cached_population_replay(
        config, baseline, promoted, taxonomy, policy, baseline_rules,
        promoted_rules, seniority_rules,
    )
    retrospective, retrospective_detail = _retrospective_replay(
        config, baseline, promoted, taxonomy, policy, baseline_rules,
        promoted_rules, seniority_rules,
    )
    gates = _promotion_gate_results(
        config, baseline, promoted, worthiness, cached, retrospective, promoted_rules,
    )
    database_hash_after = _sha256(inputs["database_path"])
    if database_hash_before != database_hash_after:
        raise CandidateDirectionAuditError("read-only audit mutated operational SQLite")
    all_pass = all(item["status"] == "PASS" for item in gates)
    run_id = run_id or (
        "candidate-direction-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
        + uuid.uuid4().hex[:8]
    )
    result = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment_id": config.experiment_id,
        "experiment_type": EXPERIMENT_TYPE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evidence_sources": {
            "accepted_specification": raw["specification"],
            "private_human_judgments_sha256": _sha256(inputs["worthiness_judgments_path"]),
            "frozen_worthiness_manifest_sha256": _sha256(inputs["worthiness_manifest_path"]),
            "retrospective_config_sha256": _sha256(inputs["retrospective_config_path"]),
        },
        "concept_audit": _enriched_concept_audit(
            config, promoted, taxonomy, promoted_rules,
        ),
        "counterfactual": {
            "frozen_worthiness_sample": worthiness,
            "compatible_cached_population": cached,
            "frozen_phase4_retrospective": retrospective,
        },
        "private_detail": {
            "frozen_worthiness_sample": worthiness_detail,
            "compatible_cached_population": cached_detail,
            "frozen_phase4_retrospective": retrospective_detail,
        },
        "fingerprints": {
            "baseline": {
                "full_profile": baseline.full_profile_fingerprint,
                "semantic_profile": baseline.semantic_profile_fingerprint,
                "scoring_preferences": baseline.scoring_preference_fingerprint,
                "market_access_policy": baseline.market_access_policy_fingerprint,
                "decision_preferences": baseline.decision_preference_fingerprint,
                "matching_rules": baseline_rules.fingerprint,
            },
            "promoted": {
                "full_profile": promoted.full_profile_fingerprint,
                "semantic_profile": promoted.semantic_profile_fingerprint,
                "scoring_preferences": promoted.scoring_preference_fingerprint,
                "market_access_policy": promoted.market_access_policy_fingerprint,
                "decision_preferences": promoted.decision_preference_fingerprint,
                "matching_rules": promoted_rules.fingerprint,
            },
        },
        "promotion_gates": gates,
        "promotion_decision": (
            "PROMOTE_VERSIONED_ACCOUNT_MANAGEMENT_AVERSION"
            if all_pass else "DO_NOT_PROMOTE"
        ),
        "stretch_envelope": {
            "runtime_implemented": False,
            "current_fit": "Core requirements are supported by current capability and experience evidence.",
            "manageable_stretch": "Important gaps coexist with transferable evidence and an explicitly desired direction, making deeper assessment potentially valuable.",
            "excessive_stretch": "Core profession, seniority, or specialist domain requires substantial requalification before candidacy is realistic.",
            "future_evidence_required": [
                "explicit core job requirements", "candidate capability levels and confidence",
                "transferable experience evidence", "required seniority/professional identity",
                "candidate direction evidence independent of capability",
            ],
            "preference_is_not_capability_proxy": True,
        },
        "portability": {
            "profile_id": portability.profile_id,
            "loaded_with_same_schema": True,
            "candidate_specific_python_branches": 0,
        },
        "integrity": {
            "database_sha256_before": database_hash_before,
            "database_sha256_after": database_hash_after,
            "database_unchanged": True,
            "semantic_calls": 0,
            "live_source_calls": 0,
            "sqlite_writes": 0,
            "semantic_profile_unchanged": baseline.semantic_profile_fingerprint == promoted.semantic_profile_fingerprint,
            "scoring_preferences_unchanged": baseline.scoring_preference_fingerprint == promoted.scoring_preference_fingerprint,
            "market_policy_unchanged": baseline.market_access_policy_fingerprint == promoted.market_access_policy_fingerprint,
            "clustering_unchanged": not retrospective["cluster_membership_changed"],
            "git": _git_state(),
        },
        "limitations": [
            "The 60-item human sample is exploratory, employer-balanced only after cap relaxation, and contains three WORTH labels.",
            "Title-only matching prioritizes precision and may miss account-management work hidden behind unrelated titles.",
            "The current compatible semantic population is small and reflects cached local evidence rather than an unbiased market sample.",
            "No stretch classifier, automation-risk matcher, semantic change, or production rejection rule is introduced.",
            "Promotion remains reviewable and reversible through candidate preference versioning.",
        ],
    }
    if write_artifact:
        root = Path(output_root or raw["outputs"]["root"])
        directory = root / run_id
        directory.mkdir(parents=True, exist_ok=False)
        detail_path = directory / "audit.json"
        detail_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        aggregate = build_sanitized_summary(result, _sha256(detail_path))
        aggregate_path = directory / "aggregate_summary.json"
        aggregate_path.write_text(
            json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        result["artifact_paths"] = {
            "private_detailed": str(detail_path),
            "repository_safe_aggregate": str(aggregate_path),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only candidate-direction preference promotion audit",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-root")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run_candidate_direction_audit(
        args.config, args.output_root, run_id=args.run_id,
        write_artifact=not args.dry_run,
    )
    print(json.dumps({
        "run_id": result["run_id"],
        "promotion_decision": result["promotion_decision"],
        "promotion_gates": result["promotion_gates"],
        "counterfactual": result["counterfactual"],
        "semantic_calls": 0,
        "artifact_paths": result.get("artifact_paths"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
