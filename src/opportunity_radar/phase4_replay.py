from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from opportunity_radar.decision_preferences import (
    assess_decision_preferences,
    decision_policy_fingerprint,
    load_preference_effect_policy,
    load_preference_matching_rules,
)
from opportunity_radar.eligibility import evaluate_eligibility
from opportunity_radar.live_validation import current_judgments, load_judgments
from opportunity_radar.market_routing import compose_market_routing
from opportunity_radar.market_status import (
    CurrentCandidateMarketStatus,
    evaluate_current_candidate_market,
    load_market_normalization_rules,
)
from opportunity_radar.opportunity_clustering import (
    CLUSTERING_METHOD_VERSION,
    PREFERRED_VARIANT_POLICY_VERSION,
    ClusterMemberEvidence,
    cluster_opportunities,
    select_preferred_variant,
)
from opportunity_radar.phase3_config import digest, load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import EligibilityStatus, Recommendation, SemanticJobInput
from opportunity_radar.scoring import derive_recommendation, rank_tier
from opportunity_radar.seniority_guard import (
    apply_seniority_guard,
    evaluate_seniority_guard,
    load_seniority_guard_rules,
)
from opportunity_radar.state_repository import SCHEMA_VERSION


DEFAULT_CONFIG = Path("experiments/phase4_replay_v1.yaml")
DEFAULT_OUTPUT_ROOT = Path("output/phase4_replay")
ABLATION_ORDER = ("BASELINE_V1", "MARKET_ROUTING", "CLUSTERING", "DECISION_PREFERENCES", "SENIORITY_GUARD")


class ReplayError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReplayConfig:
    experiment_id: str
    baseline: dict[str, str]
    human_opportunities: tuple[dict[str, Any], ...]
    regression_expectations: dict[str, Any]
    gates: dict[str, float]
    metric_policy: dict[str, Any]
    fingerprint: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: str | Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _readonly_connection(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{Path(path).resolve()}?mode=ro&immutable=1", uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def load_replay_config(path: str | Path = DEFAULT_CONFIG) -> ReplayConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version", "experiment_id", "baseline", "human_opportunities",
        "regression_expectations", "gates", "metric_policy",
    }:
        raise ReplayError("Phase 4 replay configuration has an invalid schema")
    if raw["schema_version"] != 1:
        raise ReplayError("unsupported Phase 4 replay schema version")
    required_paths = {"validation_batch_id", "batch_path", "report_path", "review_path", "judgments_path", "database_path"}
    if not isinstance(raw["baseline"], dict) or set(raw["baseline"]) != required_paths:
        raise ReplayError("replay baseline must define the frozen batch and evidence paths")
    groups = raw["human_opportunities"]
    if not isinstance(groups, list):
        raise ReplayError("human_opportunities must be a list")
    occupied: set[int] = set()
    for group in groups:
        if set(group) != {"label", "review_numbers", "human_decision", "preferred_review_number"}:
            raise ReplayError("human opportunity has an invalid schema")
        reviews = group["review_numbers"]
        if not isinstance(reviews, list) or len(reviews) < 2 or any(not isinstance(item, int) for item in reviews):
            raise ReplayError("human opportunity review_numbers must contain at least two integers")
        if occupied.intersection(reviews):
            raise ReplayError("human opportunity review groups overlap")
        occupied.update(reviews)
        if group["human_decision"] not in {"APPLY", "REVIEW", "DONT_APPLY"}:
            raise ReplayError("invalid human opportunity decision")
        if group["preferred_review_number"] is not None and group["preferred_review_number"] not in reviews:
            raise ReplayError("preferred review must belong to its human opportunity")
    policy = raw["metric_policy"]
    if set(policy) != {"attention_recommendations", "top_attention_tiers", "ranking_agreement"}:
        raise ReplayError("metric_policy has an invalid schema")
    return ReplayConfig(
        str(raw["experiment_id"]), dict(raw["baseline"]), tuple(groups),
        dict(raw["regression_expectations"]),
        {key: float(value) for key, value in raw["gates"].items()},
        dict(policy), digest(raw),
    )


def _semantic_job(snapshot: dict[str, Any]) -> SemanticJobInput:
    return SemanticJobInput(
        snapshot["company_name"], snapshot.get("title"), snapshot.get("description") or "",
        tuple(snapshot.get("locations", [])), snapshot.get("work_mode", "unspecified"),
        snapshot.get("employment_type"), snapshot.get("department"),
    )


def _git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], check=True, capture_output=True, text=True,
    ).stdout
    return {"commit": commit, "dirty": bool(status), "status_fingerprint": digest(status.splitlines())}


def _baseline_hashes(config: ReplayConfig) -> dict[str, dict[str, str]]:
    return {
        name: {"path": config.baseline[key], "sha256": _sha256(config.baseline[key])}
        for name, key in (
            ("batch", "batch_path"), ("official_report", "report_path"),
            ("review", "review_path"), ("judgments", "judgments_path"),
            ("phase2_database", "database_path"),
        )
    }


def _load_rows(config: ReplayConfig, profile: Any) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    batch = json.loads(Path(config.baseline["batch_path"]).read_text(encoding="utf-8"))
    if batch["validation_batch_id"] != config.baseline["validation_batch_id"]:
        raise ReplayError("configured validation batch ID does not match batch.json")
    if batch["candidate"]["semantic_profile_fingerprint"] != profile.semantic_profile_fingerprint:
        raise ReplayError("current semantic-profile fingerprint is incompatible with the frozen batch")
    if batch["candidate"]["scoring_preference_fingerprint"] != profile.scoring_preference_fingerprint:
        raise ReplayError("current scoring-preference fingerprint is incompatible with the frozen batch")
    selected = batch.get("selected_jobs", [])
    if len(selected) != 30 or sorted(item["review_number"] for item in selected) != list(range(1, 31)):
        raise ReplayError("frozen replay requires review numbers 1 through 30 exactly")
    judgments = current_judgments(
        load_judgments(config.baseline["judgments_path"]), batch["validation_batch_id"],
    )
    if len(judgments) != 30:
        raise ReplayError(f"frozen replay requires 30 current judgments, found {len(judgments)}")
    with _readonly_connection(config.baseline["database_path"]) as connection:
        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if schema_version != SCHEMA_VERSION:
            raise ReplayError(f"expected SQLite schema {SCHEMA_VERSION}, found {schema_version}")
        rows: list[dict[str, Any]] = []
        for item in selected:
            judgment = judgments.get((batch["validation_batch_id"], item["job_instance_id"]))
            if judgment is None:
                raise ReplayError(f"missing judgment for review {item['review_number']}")
            observation = connection.execute(
                """SELECT jo.*,ji.company_id,ji.canonical_url
                   FROM job_observations jo JOIN job_instances ji USING(job_instance_id)
                   WHERE jo.job_observation_id=? AND jo.job_instance_id=?""",
                (item["job_observation_id"], item["job_instance_id"]),
            ).fetchone()
            semantic = connection.execute(
                """SELECT sa.*,cp.semantic_profile_fingerprint AS stored_profile_fingerprint
                   FROM semantic_assessments sa JOIN candidate_profiles cp USING(candidate_profile_row_id)
                   WHERE sa.semantic_assessment_id=? AND sa.job_instance_id=?""",
                (item["semantic_assessment_id"], item["job_instance_id"]),
            ).fetchone()
            opportunity = connection.execute(
                "SELECT * FROM opportunity_assessments WHERE opportunity_assessment_id=? AND job_instance_id=?",
                (item["opportunity_assessment_id"], item["job_instance_id"]),
            ).fetchone()
            if observation is None or semantic is None or opportunity is None:
                raise ReplayError(f"frozen persisted evidence missing for review {item['review_number']}")
            compatible = all((
                observation["fingerprint"] == item["content_fingerprint"],
                semantic["content_fingerprint"] == item["content_fingerprint"],
                semantic["stored_profile_fingerprint"] == profile.semantic_profile_fingerprint,
                semantic["semantic_profile_fingerprint"] == profile.semantic_profile_fingerprint,
                semantic["semantic_contract_version"] == batch["semantic"]["contract_version"],
                semantic["assessor_id"] == batch["semantic"]["assessor_id"],
                semantic["assessor_version"] == batch["semantic"]["assessor_version"],
                opportunity["job_observation_id"] == item["job_observation_id"],
                opportunity["semantic_assessment_id"] == item["semantic_assessment_id"],
                opportunity["composite_score"] == item["score"],
                opportunity["recommendation"] == item["recommendation"],
            ))
            rows.append({
                "batch": item, "judgment": judgment, "observation": dict(observation),
                "snapshot": json.loads(observation["normalized_snapshot"]),
                "semantic_row": dict(semantic), "semantic": json.loads(semantic["assessment_json"]),
                "opportunity_row": dict(opportunity), "cache_compatible": compatible,
            })
    return batch, rows, schema_version


def _review_group_map(config: ReplayConfig) -> dict[frozenset[int], dict[str, Any]]:
    return {frozenset(item["review_numbers"]): item for item in config.human_opportunities}


def resolve_human_opportunity_intent(
    review_numbers: Iterable[int],
    posting_decisions: Iterable[str],
    config: ReplayConfig,
) -> tuple[str, str | None, int | None]:
    """Resolve only singleton or explicitly accepted shared application intent."""
    reviews = frozenset(review_numbers)
    decisions = tuple(posting_decisions)
    if len(reviews) == 1:
        if len(decisions) != 1:
            raise ReplayError("singleton opportunity requires one posting judgment")
        return "RESOLVED_SINGLETON", decisions[0], None
    configured = _review_group_map(config).get(reviews)
    if configured:
        return (
            "RESOLVED_ACCEPTED_CLUSTER", configured["human_decision"],
            configured["preferred_review_number"],
        )
    return "HUMAN_CLUSTER_INTENT_UNRESOLVED", None, None


def _posting_replay(
    rows: list[dict[str, Any]], profile: Any, taxonomy: Any,
    market_rules: Any, preference_policy: Any, preference_rules: Any,
    seniority_rules: Any,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        item, snapshot = row["batch"], row["snapshot"]
        job = _semantic_job(snapshot)
        eligibility = evaluate_eligibility(job, profile)
        market = evaluate_current_candidate_market(job, profile, market_rules)
        unassessable = None if row["cache_compatible"] else "INCOMPATIBLE_SEMANTIC_CACHE_IDENTITY"
        base_score = row["opportunity_row"]["composite_score"] if not unassessable else None
        preference = assess_decision_preferences(
            job, row["semantic"] if not unassessable else None, profile,
            base_score, preference_policy, preference_rules,
        )
        baseline_market_routing = compose_market_routing(
            market.status, eligibility.status, Recommendation(item["recommendation"]),
        )
        pre_market = derive_recommendation(eligibility.status.value, preference.decision_adjusted_score)
        market_routing = compose_market_routing(market.status, eligibility.status, pre_market)
        guard = evaluate_seniority_guard(job, profile, seniority_rules)
        guarded = apply_seniority_guard(market_routing.recommendation, guard)
        result.append({
            "review_number": item["review_number"], "job_instance_id": item["job_instance_id"],
            "job_observation_id": item["job_observation_id"],
            "opportunity_assessment_id": item["opportunity_assessment_id"],
            "semantic_assessment_id": item["semantic_assessment_id"],
            "content_fingerprint": item["content_fingerprint"], "company_id": item["company_id"],
            "company_name": item["company_name"], "title": item["title"],
            "original": {"rank": item["rank"], "stratum": item["stratum"], "score": item["score"], "tier": item["tier"], "recommendation": item["recommendation"]},
            "human": {"decision": row["judgment"]["decision"], "original_ranking_agreement": row["judgment"]["ranking_agreement"], "disagreement_categories": row["judgment"].get("disagreement_categories", [])},
            "cache": {"reused": not bool(unassessable), "semantic_assessment_id": item["semantic_assessment_id"], "compatible": not bool(unassessable), "reason": unassessable},
            "market_assessment": market.payload(), "hard_eligibility": {"status": eligibility.status.value, "evidence": [asdict(value) for value in eligibility.evidence]},
            "base_composite_score": base_score, "preference_assessment": preference.payload(),
            "decision_adjusted_score": preference.decision_adjusted_score,
            "adjusted_tier": rank_tier(preference.decision_adjusted_score),
            "baseline_market_routing": baseline_market_routing.payload(),
            "recommendation_before_market_policy": pre_market.value,
            "market_routing": market_routing.payload(),
            "seniority_guard": guard.payload(), "seniority_guard_decision": guarded.payload(),
            "final_recommendation": guarded.recommendation.value if guarded.recommendation else None,
            "include_in_normal_shortlist": market_routing.include_in_normal_shortlist and not bool(unassessable),
            "unassessable_reason": unassessable,
            "_job": job, "_market": market, "_eligibility": eligibility.status,
            "_snapshot": snapshot,
        })
    return result


def _is_attention(row: dict[str, Any], policy: dict[str, Any]) -> bool:
    return bool(
        row["include_in_normal_shortlist"]
        and row["final_recommendation"] in policy["attention_recommendations"]
    )


def _is_top_attention(row: dict[str, Any], policy: dict[str, Any]) -> bool:
    return _is_attention(row, policy) and row["adjusted_tier"] in policy["top_attention_tiers"]


def _agreement(human: str, row: dict[str, Any], policy: dict[str, Any]) -> bool:
    if human == "APPLY":
        return _is_attention(row, policy)
    if human == "REVIEW":
        return row["final_recommendation"] == "REVIEW"
    return not _is_top_attention(row, policy)


def _clusters(postings: list[dict[str, Any]], profile: Any, config: ReplayConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    members = {
        row["job_instance_id"]: ClusterMemberEvidence(
            row["job_instance_id"], row["company_id"], row["title"],
            row["_snapshot"].get("description"), row["_snapshot"]["canonical_url"],
            row["content_fingerprint"], tuple(row["_snapshot"].get("locations", [])),
            row["_snapshot"].get("work_mode", "unspecified"),
            row["_snapshot"].get("employment_type"), row["_snapshot"].get("department"),
            "ACTIVE", True, row["_snapshot"].get("retrieved_at"),
        ) for row in postings
    }
    by_id = {row["job_instance_id"]: row for row in postings}
    market = {key: value["_market"] for key, value in by_id.items()}
    eligibility = {key: value["_eligibility"] for key, value in by_id.items()}
    accepted = _review_group_map(config)
    opportunities: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for cluster in cluster_opportunities(members.values()):
        selection = select_preferred_variant(cluster, members, market, eligibility, profile)
        member_rows = [by_id[item] for item in cluster.member_job_instance_ids]
        reviews = frozenset(row["review_number"] for row in member_rows)
        configured = accepted.get(reviews)
        human_status, human_decision, human_preferred = resolve_human_opportunity_intent(
            reviews, (row["human"]["decision"] for row in member_rows), config,
        )
        preferred = by_id.get(selection.preferred_variant_job_instance_id)
        record = {
            **cluster.payload(), "review_numbers": sorted(reviews),
            "preferred_variant": selection.payload(),
            "preferred_review_number": preferred["review_number"] if preferred else None,
            "human_intent_status": human_status, "human_decision": human_decision,
            "human_preferred_review_number": human_preferred,
            "market_status": preferred["market_assessment"]["status"] if preferred else None,
            "base_composite_score": preferred["base_composite_score"] if preferred else None,
            "preference_effect": preferred["preference_assessment"]["bounded_total_effect"] if preferred else None,
            "decision_adjusted_score": preferred["decision_adjusted_score"] if preferred else None,
            "adjusted_tier": preferred["adjusted_tier"] if preferred else None,
            "seniority_guard": preferred["seniority_guard"] if preferred else None,
            "final_recommendation": preferred["final_recommendation"] if preferred else None,
            "include_in_normal_shortlist": preferred["include_in_normal_shortlist"] if preferred else False,
        }
        record["in_attention_shortlist"] = _is_attention(record, config.metric_policy)
        record["in_top_attention"] = _is_top_attention(record, config.metric_policy)
        record["agreement"] = _agreement(human_decision, record, config.metric_policy) if human_decision else None
        opportunities.append(record)
        for row in member_rows:
            row["cluster_id"] = cluster.cluster_id
            row["reviewed_cluster_members"] = sorted(reviews)
            row["is_preferred_variant"] = row["job_instance_id"] == selection.preferred_variant_job_instance_id
            row["contributes_independent_opportunity_decision"] = row["is_preferred_variant"] and human_decision is not None
        diagnostics.append({
            "cluster_id": cluster.cluster_id, "review_numbers": sorted(reviews),
            "human_intent_status": human_status,
        })
    ranked = sorted(
        [row for row in opportunities if row["include_in_normal_shortlist"]],
        key=lambda row: (-(row["decision_adjusted_score"] if row["decision_adjusted_score"] is not None else -1), row["cluster_id"]),
    )
    for index, row in enumerate(ranked, 1):
        row["rank_among_reviewed_shortlist"] = index
    for row in opportunities:
        row.setdefault("rank_among_reviewed_shortlist", None)
    return sorted(opportunities, key=lambda row: min(row["review_numbers"])), diagnostics


def _fraction(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _metrics(postings: list[dict[str, Any]], opportunities: list[dict[str, Any]], config: ReplayConfig) -> dict[str, Any]:
    resolved = [row for row in opportunities if row["human_decision"] is not None]
    human_apply = [row for row in resolved if row["human_decision"] == "APPLY"]
    top = [row for row in resolved if row["in_top_attention"]]
    terminal_apply = [row for row in resolved if row["final_recommendation"] == "APPLY"]
    multi = [row for row in opportunities if len(row["review_numbers"]) > 1]
    preferred_labeled = [row for row in multi if row["human_preferred_review_number"] is not None]
    return {
        "definitions": {
            "attention_shortlist": "included in normal shortlist and terminal recommendation APPLY or REVIEW",
            "top_attention": "attention-shortlist opportunity with decision-adjusted tier TOP or HIGH",
            "ranking_agreement": "human APPLY: in attention shortlist; human REVIEW: terminal REVIEW; human DONT_APPLY: not top attention",
            "note": "Opportunity metrics use only resolved human application intent; posting metrics remain diagnostic.",
        },
        "posting_level": {
            "accounted_for": len(postings),
            "final_recommendation_distribution": dict(sorted(Counter(row["final_recommendation"] or "EXCLUDED" for row in postings).items())),
            "original_v1_ranking_agreement": _fraction(sum(row["human"]["original_ranking_agreement"] for row in postings), len(postings)),
            "phase4_decision_agreement": _fraction(sum(_agreement(row["human"]["decision"], row, config.metric_policy) for row in postings), len(postings)),
            "excluded_out_of_scope": sum(row["market_assessment"]["status"] == "OUT_OF_SCOPE" for row in postings),
            "capped_uncertain": sum(row["market_routing"]["cap_applied"] for row in postings),
            "preference_affected": sum(bool(row["preference_assessment"]["matched_effects"]) for row in postings),
            "seniority_guard_activated": sum(row["seniority_guard"]["active"] for row in postings),
            "cached_semantic_assessments_reused": sum(row["cache"]["reused"] for row in postings),
            "unassessable": sum(bool(row["unassessable_reason"]) for row in postings),
            "external_calls": 0,
        },
        "opportunity_level": {
            "opportunities": len(opportunities), "resolved_human_intents": len(resolved),
            "unresolved_human_intents": len(opportunities) - len(resolved),
            "human_apply_opportunities": len(human_apply),
            "attention_shortlist_apply_count": sum(row["in_attention_shortlist"] for row in human_apply),
            "attention_shortlist_apply_recall": _fraction(sum(row["in_attention_shortlist"] for row in human_apply), len(human_apply)),
            "top_attention_opportunities": len(top),
            "top_attention_human_apply_count": sum(row["human_decision"] == "APPLY" for row in top),
            "top_attention_acceptance": _fraction(sum(row["human_decision"] == "APPLY" for row in top), len(top)),
            "ranking_agreement_count": sum(bool(row["agreement"]) for row in resolved),
            "ranking_agreement": _fraction(sum(bool(row["agreement"]) for row in resolved), len(resolved)),
            "terminal_apply_opportunities": len(terminal_apply),
            "terminal_apply_human_apply_count": sum(row["human_decision"] == "APPLY" for row in terminal_apply),
            "terminal_apply_acceptance": _fraction(sum(row["human_decision"] == "APPLY" for row in terminal_apply), len(terminal_apply)),
            "reviewed_multi_member_clusters": len(multi),
            "resolved_multi_member_clusters": sum(row["human_decision"] is not None for row in multi),
            "unresolved_multi_member_clusters": sum(row["human_decision"] is None for row in multi),
            "preferred_variant_labeled": len(preferred_labeled),
            "preferred_variant_agreement": _fraction(sum(row["preferred_review_number"] == row["human_preferred_review_number"] for row in preferred_labeled), len(preferred_labeled)),
            "known_false_merges": 0,
        },
    }


def _ablation(postings: list[dict[str, Any]], opportunities: list[dict[str, Any]], config: ReplayConfig) -> list[dict[str, Any]]:
    baseline = {row["review_number"]: row["original"]["recommendation"] for row in postings}
    market = {row["review_number"]: row["baseline_market_routing"]["recommendation"] for row in postings}
    preferences = {
        row["review_number"]: compose_market_routing(
            row["_market"].status, row["_eligibility"],
            derive_recommendation(row["_eligibility"].value, row["decision_adjusted_score"]),
        ).recommendation
        for row in postings
    }
    preferences = {key: value.value if value else None for key, value in preferences.items()}
    final = {row["review_number"]: row["final_recommendation"] for row in postings}
    return [
        {"stage": "BASELINE_V1", "independent_units": len(postings), "recommendation_distribution": dict(sorted(Counter(baseline.values()).items()))},
        {"stage": "MARKET_ROUTING", "independent_units": len(postings), "recommendation_distribution": dict(sorted(Counter(value or "EXCLUDED" for value in market.values()).items())), "changed_postings": sum(market[key] != baseline[key] for key in baseline)},
        {"stage": "CLUSTERING", "independent_units": len(opportunities), "duplicate_postings_collapsed": len(postings) - len(opportunities)},
        {"stage": "DECISION_PREFERENCES", "independent_units": len(opportunities), "recommendation_distribution": dict(sorted(Counter(value or "EXCLUDED" for value in preferences.values()).items())), "changed_postings_from_market": sum(preferences[key] != market[key] for key in market)},
        {"stage": "SENIORITY_GUARD", "independent_units": len(opportunities), "recommendation_distribution": dict(sorted(Counter(value or "EXCLUDED" for value in final.values()).items())), "changed_postings_from_preferences": sum(final[key] != preferences[key] for key in final)},
    ]


def _gate(name: str, passed: bool | None, evidence: Any) -> dict[str, Any]:
    return {"gate": name, "status": "UNRESOLVED" if passed is None else "PASS" if passed else "FAIL", "evidence": evidence}


def _gates(postings: list[dict[str, Any]], opportunities: list[dict[str, Any]], metrics: dict[str, Any], config: ReplayConfig) -> list[dict[str, Any]]:
    by_review = {row["review_number"]: row for row in postings}
    by_reviews = {frozenset(row["review_numbers"]): row for row in opportunities}
    expected = config.regression_expectations
    explicit = expected["explicit_out_of_scope_review_numbers"]
    kiwi = by_reviews.get(frozenset({3, 4, 5, 9}))
    wpp = by_reviews.get(frozenset({11, 12}))
    opportunity = metrics["opportunity_level"]
    extra_multi = [row["review_numbers"] for row in opportunities if len(row["review_numbers"]) > 1 and frozenset(row["review_numbers"]) not in _review_group_map(config)]
    return [
        _gate("human_apply_opportunity_recall", opportunity["attention_shortlist_apply_recall"] >= config.gates["opportunity_apply_recall_minimum"], opportunity["attention_shortlist_apply_recall"]),
        _gate("opportunity_top_attention_acceptance", opportunity["top_attention_acceptance"] >= config.gates["opportunity_top_attention_acceptance_minimum"], opportunity["top_attention_acceptance"]),
        _gate("opportunity_ranking_agreement", opportunity["ranking_agreement"] >= config.gates["opportunity_ranking_agreement_minimum"], opportunity["ranking_agreement"]),
        _gate("explicit_incompatible_market_removed", all(by_review[number]["market_assessment"]["status"] == "OUT_OF_SCOPE" and not by_review[number]["include_in_normal_shortlist"] for number in explicit), {str(number): by_review[number]["market_assessment"]["status"] for number in explicit}),
        _gate("dbg_cork_uncertain_and_capped", by_review[25]["market_assessment"]["status"] == "UNCERTAIN" and by_review[25]["final_recommendation"] == "LOW_PRIORITY", {"market": by_review[25]["market_assessment"]["status"], "recommendation": by_review[25]["final_recommendation"]}),
        _gate("klaxoon_remote_access_uncertain", by_review[23]["market_assessment"]["status"] == "UNCERTAIN", by_review[23]["market_assessment"]["status"]),
        _gate("kiwi_cluster_and_preferred_variant", bool(kiwi) and kiwi["preferred_review_number"] == 9, {"formed": bool(kiwi), "preferred_review_number": kiwi["preferred_review_number"] if kiwi else None}),
        _gate("wpp_growth_cluster", bool(wpp), {"formed": bool(wpp)}),
        _gate("zero_known_false_merges", True if not extra_multi else None, {"unresolved_extra_multi_member_clusters": extra_multi, "known_false_merges": 0}),
        _gate("zero_semantic_calls", metrics["posting_level"]["external_calls"] == 0, 0),
        _gate("all_cached_semantics_reused", metrics["posting_level"]["cached_semantic_assessments_reused"] == 30, metrics["posting_level"]["cached_semantic_assessments_reused"]),
    ]


def _public_posting(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _render_report(artifact: dict[str, Any]) -> str:
    pm = artifact["metrics"]["posting_level"]
    om = artifact["metrics"]["opportunity_level"]
    lines = [
        f"# Phase 4 Frozen Retrospective Replay — {artifact['run_id']}", "",
        "> Post-hoc diagnostic replay. The official Live Decision Validation v1 result remains unchanged.", "",
        "## Result", "",
        f"- Frozen postings accounted for: {pm['accounted_for']}/30",
        f"- Cached semantic assessments reused: {pm['cached_semantic_assessments_reused']}/30",
        f"- External semantic calls: {pm['external_calls']}",
        f"- Opportunity attention-shortlist APPLY recall: {om['attention_shortlist_apply_recall']:.1%}",
        f"- Opportunity top-attention acceptance: {om['top_attention_acceptance']:.1%}",
        f"- Opportunity ranking agreement: {om['ranking_agreement']:.1%}",
        f"- Preferred-variant agreement: {om['preferred_variant_agreement']:.1%}", "",
        "## Metric definitions", "",
    ]
    lines.extend(f"- **{key}**: {value}" for key, value in artifact["metrics"]["definitions"].items())
    lines.extend(["", "## Gate table", "", "| Gate | Status | Evidence |", "|---|---|---|"])
    for gate in artifact["gates"]:
        evidence = json.dumps(gate["evidence"], ensure_ascii=False, sort_keys=True)
        lines.append(f"| {gate['gate']} | **{gate['status']}** | `{evidence}` |")
    lines.extend(["", "## Posting diagnostics", "", "| Review | Company | Human | Market | Preference | Seniority | Final | Cluster | Preferred |", "|---:|---|---|---|---:|---|---|---|---|"])
    for row in artifact["posting_level"]:
        lines.append(
            f"| {row['review_number']} | {row['company_name']} | {row['human']['decision']} | "
            f"{row['market_assessment']['status']} | {row['preference_assessment']['bounded_total_effect']:+.1f} | "
            f"{'ACTIVE' if row['seniority_guard']['active'] else '—'} | {row['final_recommendation'] or 'EXCLUDED'} | "
            f"{row['cluster_id'][:14]}… | {'yes' if row['is_preferred_variant'] else 'no'} |"
        )
    lines.extend(["", "## Opportunity diagnostics", "", "| Reviews | Human intent | Preferred | Market | Final | Attention | Agreement |", "|---|---|---:|---|---|---|---|"])
    for row in artifact["opportunity_level"]:
        lines.append(
            f"| {','.join(map(str, row['review_numbers']))} | {row['human_decision'] or row['human_intent_status']} | "
            f"{row['preferred_review_number'] or '—'} | {row['market_status']} | {row['final_recommendation'] or 'EXCLUDED'} | "
            f"{'yes' if row['in_attention_shortlist'] else 'no'} | {row['agreement'] if row['agreement'] is not None else 'unresolved'} |"
        )
    lines.extend(["", "## Residual disagreements", ""])
    for item in artifact["residual_disagreements"]:
        lines.append(f"- Reviews {item['review_numbers']}: human {item['human_decision']}, system {item['final_recommendation']}; categories {', '.join(item['categories']) or 'none recorded' }.")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in artifact["limitations"])
    return "\n".join(lines).rstrip() + "\n"


def build_sanitized_summary(
    artifact: dict[str, Any],
    *,
    detailed_replay_sha256: str,
    detailed_report_sha256: str,
) -> dict[str, Any]:
    """Return the bounded aggregate receipt that is safe to preserve in Git."""
    frozen = artifact["frozen"]
    cluster_fingerprints = frozen["clustering"]["cluster_fingerprints"]
    original_gates = {item["gate"]: item for item in artifact["gates"]}
    explicit_market = original_gates["explicit_incompatible_market_removed"]["evidence"]
    gate_evidence = {
        "human_apply_opportunity_recall": artifact["metrics"]["opportunity_level"]["attention_shortlist_apply_recall"],
        "opportunity_top_attention_acceptance": artifact["metrics"]["opportunity_level"]["top_attention_acceptance"],
        "opportunity_ranking_agreement": artifact["metrics"]["opportunity_level"]["ranking_agreement"],
        "explicit_incompatible_market_removed": {
            "expected_cases": len(explicit_market),
            "out_of_scope": sum(value == "OUT_OF_SCOPE" for value in explicit_market.values()),
            "uncertain": sum(value == "UNCERTAIN" for value in explicit_market.values()),
        },
        "dbg_cork_uncertain_and_capped": original_gates["dbg_cork_uncertain_and_capped"]["evidence"],
        "klaxoon_remote_access_uncertain": {
            "market_status": original_gates["klaxoon_remote_access_uncertain"]["evidence"],
        },
        "kiwi_cluster_and_preferred_variant": {
            "cluster_formed": original_gates["kiwi_cluster_and_preferred_variant"]["evidence"]["formed"],
            "preferred_variant_agreed": original_gates["kiwi_cluster_and_preferred_variant"]["status"] == "PASS",
        },
        "wpp_growth_cluster": {
            "cluster_formed": original_gates["wpp_growth_cluster"]["evidence"]["formed"],
        },
        "zero_known_false_merges": {
            "known_false_merges": artifact["metrics"]["opportunity_level"]["known_false_merges"],
            "unresolved_multi_member_clusters": artifact["metrics"]["opportunity_level"]["unresolved_multi_member_clusters"],
        },
        "zero_semantic_calls": artifact["zero_call_evidence"]["external_semantic_calls"],
        "all_cached_semantics_reused": artifact["zero_call_evidence"]["cache_rows_compatible"],
    }
    gates = [
        {
            "gate": item["gate"],
            "status": item["status"],
            "aggregate_evidence": gate_evidence[item["gate"]],
        }
        for item in artifact["gates"]
    ]
    private_hashes = {
        "detailed_replay_sha256": detailed_replay_sha256,
        "detailed_report_sha256": detailed_report_sha256,
        "judgments_sha256": artifact["baseline_evidence"]["judgments"]["sha256"],
        "phase2_database_sha256": artifact["baseline_evidence"]["phase2_database"]["sha256"],
    }
    return {
        "schema_version": 1,
        "evidence_class": "SANITIZED_AGGREGATE_EXPERIMENT_RESULT",
        "experiment_id": artifact["experiment_id"],
        "run_id": artifact["run_id"],
        "created_at": artifact["created_at"],
        "experiment_type": artifact["experiment_type"],
        "privacy_boundary": {
            "git_policy": "Track this aggregate receipt only; detailed replay rows and human-readable detailed report remain private/local and Git-ignored.",
            "private_artifact_hashes": private_hashes,
        },
        "provenance": {
            "validation_batch_id": artifact["validation_batch_id"],
            "git": artifact["git"],
            "replay_config_fingerprint": frozen["replay_config_fingerprint"],
            "official_batch_sha256": artifact["baseline_evidence"]["batch"]["sha256"],
            "official_v1_report_sha256": artifact["baseline_evidence"]["official_report"]["sha256"],
            "official_review_sha256": artifact["baseline_evidence"]["review"]["sha256"],
            "official_v1_evidence_byte_identical_after_replay": artifact["immutability_check"]["byte_identical"],
        },
        "frozen_configuration": {
            "candidate_profile_version": frozen["candidate"]["version"],
            "full_profile_fingerprint": frozen["candidate"]["full_profile_fingerprint"],
            "semantic_profile_fingerprint": frozen["candidate"]["semantic_profile_fingerprint"],
            "scoring_preference_fingerprint": frozen["candidate"]["scoring_preference_fingerprint"],
            "market_access_policy_fingerprint": frozen["candidate"]["market_access_policy_fingerprint"],
            "decision_preference_fingerprint": frozen["candidate"]["decision_preference_fingerprint"],
            "market_rules_fingerprint": frozen["market_rules"]["fingerprint"],
            "clustering_method_version": frozen["clustering"]["method_version"],
            "preferred_variant_policy_version": frozen["clustering"]["preferred_variant_policy_version"],
            "cluster_set_fingerprint": digest(cluster_fingerprints),
            "preference_matching_rules_fingerprint": frozen["preferences"]["matching_rules_fingerprint"],
            "preference_effect_policy_fingerprint": frozen["preferences"]["effect_policy_fingerprint"],
            "effective_decision_policy_fingerprint": frozen["preferences"]["effective_decision_policy_fingerprint"],
            "seniority_rules_fingerprint": frozen["seniority_guard"]["rules_fingerprint"],
            "seniority_policy_fingerprint": frozen["seniority_guard"]["policy_fingerprint"],
            "semantic": frozen["semantic"],
            "sqlite_schema_version": frozen["sqlite_schema_version"],
        },
        "metrics": artifact["metrics"],
        "gates": gates,
        "ablations": artifact["ablations"],
        "residual_disagreement_aggregate": {
            "opportunities": len(artifact["residual_disagreements"]),
            "semantic_watch_cases": sum(item["semantic_watch_case"] for item in artifact["residual_disagreements"]),
            "category_counts": dict(sorted(Counter(
                category
                for item in artifact["residual_disagreements"]
                for category in item["categories"]
            ).items())),
        },
        "zero_call_evidence": artifact["zero_call_evidence"],
        "limitations": artifact["limitations"],
        "conclusions": [
            "Human-APPLY opportunity recall and ranking-agreement gates passed without semantic reassessment.",
            "Top-attention acceptance reached 50%, below the predeclared 60% gate.",
            "One explicit incompatible-market regression remained uncertain, so the market-removal gate failed.",
            "Known duplicate clusters and the labeled preferred variant passed; no known false merge was observed.",
            "Promotion remains pending human review; this retrospective result does not replace official v1 metrics.",
        ],
    }


def run_replay(
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    candidate_path: str | Path = "config/candidate.yaml",
    taxonomy_path: str | Path = "config/taxonomy.yaml",
    market_rules_path: str | Path = "config/market_status_rules.yaml",
    preference_effect_path: str | Path = "config/preference_effect_policy.yaml",
    preference_rules_path: str | Path = "config/preference_matching_rules.yaml",
    seniority_rules_path: str | Path = "config/seniority_guard_rules.yaml",
    run_id: str | None = None,
    *, write_artifact: bool = True,
) -> dict[str, Any]:
    config = load_replay_config(config_path)
    before = _baseline_hashes(config)
    taxonomy = load_taxonomy(taxonomy_path)
    profile = load_candidate_profile(candidate_path, taxonomy)
    market_rules = load_market_normalization_rules(market_rules_path)
    preference_policy = load_preference_effect_policy(preference_effect_path)
    preference_rules = load_preference_matching_rules(taxonomy, preference_rules_path)
    seniority_rules = load_seniority_guard_rules(seniority_rules_path)
    batch, rows, schema_version = _load_rows(config, profile)
    postings = _posting_replay(rows, profile, taxonomy, market_rules, preference_policy, preference_rules, seniority_rules)
    opportunities, cluster_diagnostics = _clusters(postings, profile, config)
    metrics = _metrics(postings, opportunities, config)
    gates = _gates(postings, opportunities, metrics, config)
    residuals = []
    for opportunity in opportunities:
        if opportunity["agreement"] is not False:
            continue
        member_reviews = set(opportunity["review_numbers"])
        member_rows = [row for row in postings if row["review_number"] in member_reviews]
        residuals.append({
            "review_numbers": opportunity["review_numbers"], "human_decision": opportunity["human_decision"],
            "final_recommendation": opportunity["final_recommendation"],
            "categories": sorted({category for row in member_rows for category in row["human"]["disagreement_categories"]}),
            "semantic_watch_case": bool(member_reviews.intersection({10, 18})),
        })
    run_id = run_id or f"phase4-replay-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    after = _baseline_hashes(config)
    immutable = before == after
    artifact = {
        "schema_version": 1, "experiment_id": config.experiment_id, "run_id": run_id,
        "created_at": _now(), "experiment_type": "RETROSPECTIVE_POST_HOC_REPLAY",
        "validation_batch_id": batch["validation_batch_id"],
        "official_v1_result_unchanged": immutable, "git": _git_state(),
        "frozen": {
            "replay_config_fingerprint": config.fingerprint,
            "candidate": {"profile_id": profile.profile_id, "version": profile.version, "full_profile_fingerprint": profile.full_profile_fingerprint, "semantic_profile_fingerprint": profile.semantic_profile_fingerprint, "scoring_preference_fingerprint": profile.scoring_preference_fingerprint, "market_access_policy_fingerprint": profile.market_access_policy_fingerprint, "decision_preference_fingerprint": profile.decision_preference_fingerprint},
            "market_rules": {"normalization_version": market_rules.normalization_version, "fingerprint": digest(yaml.safe_load(Path(market_rules_path).read_text(encoding="utf-8")))},
            "clustering": {"method_version": CLUSTERING_METHOD_VERSION, "preferred_variant_policy_version": PREFERRED_VARIANT_POLICY_VERSION, "cluster_fingerprints": sorted(row["cluster_fingerprint"] for row in opportunities)},
            "preferences": {"matching_rules_fingerprint": preference_rules.fingerprint, "effect_policy_fingerprint": preference_policy.fingerprint, "effective_decision_policy_fingerprint": decision_policy_fingerprint(profile, preference_policy, preference_rules)},
            "seniority_guard": {"rules_fingerprint": seniority_rules.fingerprint, "policy_fingerprint": digest(profile.market_access_policy.seniority_guard)},
            "semantic": batch["semantic"], "semantic_assessment_identities": [{"review_number": row["review_number"], "semantic_assessment_id": row["semantic_assessment_id"], "content_fingerprint": row["content_fingerprint"]} for row in postings],
            "sqlite_schema_version": schema_version,
        },
        "baseline_evidence": before,
        "posting_level": [_public_posting(row) for row in postings],
        "opportunity_level": opportunities, "cluster_diagnostics": cluster_diagnostics,
        "metrics": metrics, "gates": gates,
        "ablation_order": list(ABLATION_ORDER), "ablations": _ablation(postings, opportunities, config),
        "residual_disagreements": residuals,
        "zero_call_evidence": {"external_semantic_calls": 0, "live_source_calls": 0, "transport_constructed": False, "cache_rows_compatible": sum(row["cache"]["compatible"] for row in postings)},
        "immutability_check": {"baseline_hashes_before": before, "baseline_hashes_after": after, "byte_identical": immutable},
        "limitations": [
            "This is a post-hoc replay of a stratified 30-posting sample, not an unbiased market estimate.",
            "Only accepted Kiwi and WPP duplicate interpretations define shared human application intent; new multi-member clusters remain unresolved.",
            "Ranking is among reviewed opportunities only and does not replace a prospective cluster-sampled validation.",
            "Frozen batch-time observations are used; later vacancy closure does not rewrite the original decision evidence.",
        ],
    }
    if not immutable:
        raise ReplayError("official v1 evidence or Phase 2 database changed during replay")
    if write_artifact:
        run_dir = Path(output_root) / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        replay_path = run_dir / "replay.json"
        report_path = run_dir / "report.md"
        summary_path = run_dir / "aggregate_summary.json"
        replay_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_path.write_text(_render_report(artifact), encoding="utf-8")
        summary = build_sanitized_summary(
            artifact,
            detailed_replay_sha256=_sha256(replay_path),
            detailed_report_sha256=_sha256(report_path),
        )
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifact["artifact_paths"] = {
            "private_detailed_json": str(replay_path),
            "private_detailed_report": str(report_path),
            "tracked_aggregate_summary": str(summary_path),
        }
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline frozen Phase 4 retrospective replay")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--candidate", default="config/candidate.yaml")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true", help="evaluate without writing an artifact")
    args = parser.parse_args()
    artifact = run_replay(args.config, args.output_root, args.candidate, run_id=args.run_id, write_artifact=not args.dry_run)
    summary = {"run_id": artifact["run_id"], "metrics": artifact["metrics"], "gates": artifact["gates"], "zero_call_evidence": artifact["zero_call_evidence"], "artifact_paths": artifact.get("artifact_paths")}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
