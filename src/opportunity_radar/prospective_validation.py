from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.live_validation import (
    ASSESSOR_ID,
    LUNA_TIER,
    _active_rows,
    _clustered_assessed_pool,
    _readonly_connection,
    build_preflight,
    observed_luna_cost,
)
from opportunity_radar.market_status import load_market_normalization_rules
from opportunity_radar.opportunity_clustering import (
    CLUSTERING_METHOD_VERSION,
    PREFERRED_VARIANT_POLICY_VERSION,
)
from opportunity_radar.phase3_config import digest, load_candidate_profile, load_taxonomy
from opportunity_radar.roi_experiment import load_experiment_config
from opportunity_radar.semantic import SEMANTIC_CONTRACT_VERSION
from opportunity_radar.seniority_guard import load_seniority_guard_rules


DEFAULT_CONFIG = Path("experiments/phase4_prospective_validation_v1.yaml")
DEFAULT_DATABASE = Path("output/opportunity_radar.sqlite3")
DEFAULT_OUTPUT_ROOT = Path("output/phase4_prospective")
ARTIFACT_TYPE = "DIAGNOSTIC_PREVIEW_NOT_PROSPECTIVE_BATCH"
CACHE_STATUSES = {
    "COMPATIBLE_SEMANTIC_CACHE_HIT",
    "SEMANTIC_CACHE_MISS",
    "SEMANTICALLY_UNASSESSABLE",
}
STRATA = (
    "TOP_ATTENTION",
    "REVIEW_BOUNDARY",
    "LOW_PRIORITY_CONTROL",
    "MARKET_CONTROL",
)
NORMAL_STRATA = STRATA[:3]


class ProspectiveValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ProspectiveProtocol:
    raw: dict[str, Any]
    fingerprint: str

    @property
    def version(self) -> str:
        return str(self.raw["protocol_version"])

    @property
    def experiment_id(self) -> str:
        return str(self.raw["experiment_id"])

    @property
    def sampling(self) -> dict[str, Any]:
        return self.raw["sampling"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: str | Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _yaml_digest(path: str | Path) -> str:
    return digest(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(x, str) for x in value):
        raise ProspectiveValidationError(f"{label} must be a non-empty string list")
    return value


def load_prospective_protocol(path: str | Path = DEFAULT_CONFIG) -> ProspectiveProtocol:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required = {
        "schema_version", "protocol_version", "experiment_id", "experiment_type",
        "candidate_path", "taxonomy_path", "semantic_config_path", "market_rules_path",
        "preference_effect_policy_path", "preference_matching_rules_path",
        "seniority_rules_path", "historical_batch_path", "roi_results_path",
        "sampling", "human_labels", "metrics", "stopping", "privacy",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise ProspectiveValidationError("prospective protocol has an invalid top-level schema")
    if raw["schema_version"] != 1:
        raise ProspectiveValidationError("unsupported prospective protocol schema version")
    if raw["experiment_type"] != "PROSPECTIVE_CLUSTER_VALIDATION":
        raise ProspectiveValidationError("invalid prospective experiment type")
    sampling = raw["sampling"]
    if not isinstance(sampling, dict) or set(sampling) != {
        "seed", "target", "reserve_per_stratum", "normal_employer_cap",
        "market_control_additional_employer_cap", "strata", "fallback_order",
    }:
        raise ProspectiveValidationError("invalid prospective sampling configuration")
    targets = sampling["strata"]
    if not isinstance(targets, dict) or tuple(targets) != STRATA:
        raise ProspectiveValidationError("prospective strata must use the frozen order")
    if sum(int(value) for value in targets.values()) != int(sampling["target"]):
        raise ProspectiveValidationError("stratum targets must sum to the sample target")
    if int(sampling["target"]) != 40 or [int(targets[x]) for x in STRATA] != [15, 10, 10, 5]:
        raise ProspectiveValidationError("SPEC-008 freezes a 15/10/10/5 sample")
    for stratum in STRATA:
        _require_string_list(sampling["fallback_order"].get(stratum), f"fallback_order.{stratum}")
    labels = raw["human_labels"]
    expected_labels = {
        "attention": {"YES", "NO"},
        "application_intent": {"APPLY", "DONT_APPLY", "NEED_MORE_INFO"},
        "market_status_human": {"IN_SCOPE", "UNCERTAIN", "OUT_OF_SCOPE"},
        "preferred_variant_agreement": {"AGREE", "DISAGREE", "NOT_APPLICABLE"},
        "cluster_correctness": {"CORRECT", "FALSE_MERGE", "NOT_APPLICABLE"},
    }
    if set(labels) != set(expected_labels):
        raise ProspectiveValidationError("invalid human-label fields")
    for field, expected in expected_labels.items():
        if set(_require_string_list(labels[field], f"human_labels.{field}")) != expected:
            raise ProspectiveValidationError(f"invalid controlled values for {field}")
    if raw["metrics"].get("normal_strata") != list(NORMAL_STRATA):
        raise ProspectiveValidationError("metric normal strata do not match the protocol")
    if raw["stopping"] != {
        "completed_cluster_judgments": 40,
        "early_stopping": False,
        "unavailable_item_is_ranking_disagreement": False,
        "replacement_policy": "FROZEN_RESERVE_SAME_STRATUM_ONLY",
    }:
        raise ProspectiveValidationError("stopping policy does not match SPEC-008")
    if raw["privacy"] != {
        "detailed_artifacts": "PRIVATE_LOCAL",
        "aggregate_summary": "REPOSITORY_SAFE",
    }:
        raise ProspectiveValidationError("invalid prospective privacy policy")
    return ProspectiveProtocol(raw=raw, fingerprint=digest(raw))


def historical_reviewed_job_ids(batch_path: str | Path) -> set[int]:
    batch = json.loads(Path(batch_path).read_text(encoding="utf-8"))
    result: set[int] = set()
    for item in batch.get("selected_jobs", []):
        members = item.get("member_job_instance_ids") or [item["job_instance_id"]]
        result.update(int(value) for value in members)
    return result


def mark_historical_overlap(
    population: list[dict[str, Any]], reviewed_job_ids: set[int],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    marked = []
    overlap_clusters = overlap_members = 0
    for item in population:
        overlap = sorted(set(item["member_job_instance_ids"]) & reviewed_job_ids)
        copy = dict(item, historical_reviewed_overlap=bool(overlap), historical_overlap_member_ids=overlap)
        marked.append(copy)
        if overlap:
            overlap_clusters += 1
            overlap_members += len(overlap)
    return marked, {
        "excluded_cluster_count": overlap_clusters,
        "overlapping_member_count": overlap_members,
    }


def _stable_tie(seed: str, stratum: str, cluster_id: str) -> str:
    return hashlib.sha256(f"{seed}:{stratum}:{cluster_id}".encode()).hexdigest()


def _score(item: dict[str, Any], field: str = "score") -> float:
    value = item.get(field)
    return float(value) if value is not None else -1.0


def _source_candidates(
    population: list[dict[str, Any]], source: str, stratum: str, seed: str,
) -> list[dict[str, Any]]:
    normal = [
        item for item in population
        if item.get("normal_candidate") and not item.get("historical_reviewed_overlap")
        and item.get("semantic_cache_status") == "COMPATIBLE_SEMANTIC_CACHE_HIT"
    ]
    market = [
        item for item in population
        if item.get("market_status") == "OUT_OF_SCOPE"
        and not item.get("historical_reviewed_overlap")
    ]
    if source == "SYSTEM_ATTENTION":
        values = [x for x in normal if x.get("recommendation") in {"APPLY", "REVIEW"}]
        key = lambda x: (-_score(x), _stable_tie(seed, stratum, x["cluster_id"]))
    elif source == "TERMINAL_REVIEW":
        values = [x for x in normal if x.get("recommendation") == "REVIEW"]
        key = lambda x: (abs(_score(x) - 6.0), _stable_tie(seed, stratum, x["cluster_id"]))
    elif source == "TERMINAL_LOW_PRIORITY":
        values = [x for x in normal if x.get("recommendation") == "LOW_PRIORITY"]
        key = lambda x: (-_score(x), _stable_tie(seed, stratum, x["cluster_id"]))
    elif source == "NORMAL_REMAINDER":
        values = normal
        key = lambda x: (-_score(x), _stable_tie(seed, stratum, x["cluster_id"]))
    elif source == "OUT_OF_SCOPE_WITH_BASE_FIT":
        values = [x for x in market if x.get("base_composite_score") is not None]
        key = lambda x: (-_score(x, "base_composite_score"), _stable_tie(seed, stratum, x["cluster_id"]))
    elif source == "OUT_OF_SCOPE_REMAINDER":
        values = market
        key = lambda x: (-_score(x, "base_composite_score"), _stable_tie(seed, stratum, x["cluster_id"]))
    else:
        raise ProspectiveValidationError(f"unknown fallback source: {source}")
    return sorted(values, key=key)


def _ordered_for_stratum(
    population: list[dict[str, Any]], stratum: str,
    fallback_order: list[str], seed: str,
) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in fallback_order:
        for item in _source_candidates(population, source, stratum, seed):
            if item["cluster_id"] in seen:
                continue
            seen.add(item["cluster_id"])
            ordered.append(dict(item, selection_source=source))
    return ordered


def _select_with_cap(
    candidates: list[dict[str, Any]], target: int, used: set[str],
    employer_counts: Counter[str], initial_cap: int, stratum: str,
) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    chosen: list[dict[str, Any]] = []
    cap = initial_cap
    relaxations: list[dict[str, Any]] = []
    while len(chosen) < target:
        progress = False
        for item in candidates:
            if item["cluster_id"] in used:
                continue
            if employer_counts[item["company_id"]] >= cap:
                continue
            chosen.append(dict(item, stratum=stratum))
            used.add(item["cluster_id"])
            employer_counts[item["company_id"]] += 1
            progress = True
            if len(chosen) == target:
                break
        if len(chosen) == target:
            break
        remaining = [item for item in candidates if item["cluster_id"] not in used]
        if not remaining:
            break
        if not progress:
            old = cap
            cap += 1
            relaxations.append({
                "stratum": stratum, "from_cap": old, "to_cap": cap,
                "reason": "available population could not fill the frozen target under the prior cap",
            })
    return chosen, cap, relaxations


def select_prospective_sample(
    population: list[dict[str, Any]], protocol: ProspectiveProtocol,
) -> dict[str, Any]:
    """Pure deterministic sampler. Human labels are intentionally not an input."""
    sampling = protocol.sampling
    seed = str(sampling["seed"])
    used: set[str] = set()
    selected: list[dict[str, Any]] = []
    relaxations: list[dict[str, Any]] = []
    normal_counts: Counter[str] = Counter()
    normal_cap = int(sampling["normal_employer_cap"])
    ordered_by_stratum: dict[str, list[dict[str, Any]]] = {}
    for stratum in NORMAL_STRATA:
        candidates = _ordered_for_stratum(
            population, stratum, sampling["fallback_order"][stratum], seed,
        )
        ordered_by_stratum[stratum] = candidates
        chosen, normal_cap, changes = _select_with_cap(
            candidates, int(sampling["strata"][stratum]), used,
            normal_counts, normal_cap, stratum,
        )
        selected.extend(chosen)
        relaxations.extend(changes)

    market_stratum = "MARKET_CONTROL"
    market_candidates = _ordered_for_stratum(
        population, market_stratum, sampling["fallback_order"][market_stratum], seed,
    )
    ordered_by_stratum[market_stratum] = market_candidates
    market_counts: Counter[str] = Counter()
    market, market_cap, changes = _select_with_cap(
        market_candidates, int(sampling["strata"][market_stratum]), used,
        market_counts, int(sampling["market_control_additional_employer_cap"]),
        market_stratum,
    )
    selected.extend(market)
    relaxations.extend(changes)

    reserve_count = int(sampling["reserve_per_stratum"])
    reserves: dict[str, list[dict[str, Any]]] = {}
    reserved: set[str] = set()
    for stratum in STRATA:
        values = []
        for item in ordered_by_stratum[stratum]:
            if item["cluster_id"] in used or item["cluster_id"] in reserved:
                continue
            reserved.add(item["cluster_id"])
            values.append(dict(item, stratum=stratum, reserve_order=len(values) + 1))
            if len(values) == reserve_count:
                break
        reserves[stratum] = values

    selected.sort(key=lambda item: (
        STRATA.index(item["stratum"]),
        next(
            index for index, candidate in enumerate(ordered_by_stratum[item["stratum"]])
            if candidate["cluster_id"] == item["cluster_id"]
        ),
    ))
    for index, item in enumerate(selected, 1):
        item["sample_item_id"] = f"PV-{index:03d}"
    blind_order = sorted(
        selected,
        key=lambda item: _stable_tie(seed, "BLIND_REVIEW", item["cluster_id"]),
    )
    blind_ids = [item["sample_item_id"] for item in blind_order]
    counts = Counter(item["stratum"] for item in selected)
    shortfalls = {
        stratum: int(sampling["strata"][stratum]) - counts[stratum]
        for stratum in STRATA if counts[stratum] < int(sampling["strata"][stratum])
    }
    return {
        "selected": selected,
        "reserves": reserves,
        "blind_review_order": blind_ids,
        "stratum_counts": {stratum: counts[stratum] for stratum in STRATA},
        "shortfalls": shortfalls,
        "employer_counts_normal": dict(sorted(normal_counts.items())),
        "employer_counts_market_controls": dict(sorted(market_counts.items())),
        "normal_employer_cap_initial": int(sampling["normal_employer_cap"]),
        "normal_employer_cap_effective": normal_cap,
        "market_employer_cap_initial": int(sampling["market_control_additional_employer_cap"]),
        "market_employer_cap_effective": market_cap,
        "cap_relaxations": relaxations,
    }


def semantic_cache_preflight(
    items: list[dict[str, Any]], cost_per_miss_usd: float,
) -> dict[str, Any]:
    counts = Counter(item["semantic_cache_status"] for item in items)
    unknown = set(counts) - CACHE_STATUSES
    if unknown:
        raise ProspectiveValidationError(f"unknown semantic cache statuses: {sorted(unknown)}")
    misses = counts["SEMANTIC_CACHE_MISS"]
    required_misses = sum(
        item["semantic_cache_status"] == "SEMANTIC_CACHE_MISS"
        and item.get("normal_candidate", True)
        for item in items
    )
    return {
        "compatible_cache_hits": counts["COMPATIBLE_SEMANTIC_CACHE_HIT"],
        "semantic_cache_misses": misses,
        "semantically_unassessable": counts["SEMANTICALLY_UNASSESSABLE"],
        "semantic_assessment_required_misses": required_misses,
        "non_routed_cache_misses": misses - required_misses,
        "expected_external_calls": required_misses,
        "estimated_cost_per_cache_miss_usd": round(float(cost_per_miss_usd), 8),
        "estimated_external_cost_usd": round(required_misses * float(cost_per_miss_usd), 8),
        "external_calls_made": 0,
    }


def _assessment_rows(
    connection: sqlite3.Connection, profile, assessor_version: str,
) -> dict[int, dict[str, Any]]:
    rows = connection.execute(
        """SELECT ji.job_instance_id,oa.opportunity_assessment_id,
                  oa.composite_score,oa.recommendation,
                  sa.semantic_assessment_id,sa.assessment_json
           FROM job_instances ji
           JOIN job_observations jo ON jo.job_observation_id=ji.latest_observation_id
           JOIN semantic_assessments sa
             ON sa.job_instance_id=ji.job_instance_id AND sa.content_fingerprint=jo.fingerprint
           LEFT JOIN opportunity_assessments oa ON oa.semantic_assessment_id=sa.semantic_assessment_id
           LEFT JOIN candidate_profiles cp ON cp.candidate_profile_row_id=oa.candidate_profile_row_id
           WHERE ji.lifecycle_state='ACTIVE'
             AND sa.semantic_profile_fingerprint=? AND sa.semantic_contract_version=?
             AND sa.assessor_id=? AND sa.assessor_version=?
             AND (oa.opportunity_assessment_id IS NULL OR
                  (cp.semantic_profile_fingerprint=? AND oa.scoring_preference_fingerprint=?))
           ORDER BY ji.job_instance_id,oa.opportunity_assessment_id DESC""",
        (
            profile.semantic_profile_fingerprint, SEMANTIC_CONTRACT_VERSION,
            ASSESSOR_ID, assessor_version, profile.semantic_profile_fingerprint,
            profile.scoring_preference_fingerprint,
        ),
    ).fetchall()
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        result.setdefault(int(row["job_instance_id"]), dict(row))
    return result


def build_current_cluster_population(
    database: str | Path, protocol: ProspectiveProtocol,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw = protocol.raw
    taxonomy = load_taxonomy(raw["taxonomy_path"])
    profile = load_candidate_profile(raw["candidate_path"], taxonomy)
    experiment = load_experiment_config(raw["semantic_config_path"])
    luna = experiment.models[LUNA_TIER]
    assessor_version = f"1:{luna.model}"
    market_rules = load_market_normalization_rules(raw["market_rules_path"])
    pool, diagnostics = _clustered_assessed_pool(
        database, profile, assessor_version, market_rules, taxonomy,
        raw["preference_effect_policy_path"], raw["preference_matching_rules_path"],
        raw["seniority_rules_path"],
    )
    normal_by_cluster = {item["cluster_id"]: item for item in pool}
    preflight = build_preflight(
        database, candidate_path=raw["candidate_path"], taxonomy_path=raw["taxonomy_path"],
        semantic_config_path=raw["semantic_config_path"],
        roi_results_path=raw["roi_results_path"], market_rules_path=raw["market_rules_path"],
    )
    preflight_by_job = {
        int(item["job_instance_id"]): item for item in preflight["assessable_jobs"]
    }
    with _readonly_connection(database) as connection:
        active_by_id = {int(item["job_instance_id"]): item for item in _active_rows(connection)}
        assessment_by_job = _assessment_rows(connection, profile, assessor_version)
    population: list[dict[str, Any]] = []
    for diagnostic in diagnostics:
        preferred_id = diagnostic["preferred_variant"]["preferred_variant_job_instance_id"]
        if preferred_id is None:
            continue
        preferred_id = int(preferred_id)
        active = active_by_id[preferred_id]
        snapshot = active["snapshot"]
        state = preflight_by_job.get(preferred_id)
        assessed = assessment_by_job.get(preferred_id)
        normal = normal_by_cluster.get(diagnostic["cluster_id"])
        if state is None:
            cache_status = "SEMANTICALLY_UNASSESSABLE"
        elif state["existing_semantic_cache_hit"]:
            cache_status = "COMPATIBLE_SEMANTIC_CACHE_HIT"
        else:
            cache_status = "SEMANTIC_CACHE_MISS"
        member_evidence = []
        member_summaries = {
            int(item["job_instance_id"]): item for item in diagnostic["members"]
        }
        for member_id in diagnostic["member_job_instance_ids"]:
            member_id = int(member_id)
            member = active_by_id[member_id]
            member_snapshot = member["snapshot"]
            member_evidence.append({
                **member_summaries[member_id],
                "title": member_snapshot.get("title"),
                "locations": member_snapshot.get("locations", []),
                "work_mode": member_snapshot.get("work_mode", "unspecified"),
                "canonical_url": member["canonical_url"],
            })
        population.append({
            "cluster_id": diagnostic["cluster_id"],
            "cluster_fingerprint": diagnostic["cluster_fingerprint"],
            "company_id": diagnostic["company_id"],
            "company_name": snapshot["company_name"],
            "canonical_role_identity": diagnostic["canonical_role_identity"],
            "clustering_method": diagnostic["clustering_method"],
            "clustering_method_version": diagnostic["clustering_method_version"],
            "clustering_evidence": diagnostic["clustering_evidence"],
            "member_job_instance_ids": [int(x) for x in diagnostic["member_job_instance_ids"]],
            "member_count": len(diagnostic["member_job_instance_ids"]),
            "cluster_members": member_evidence,
            "preferred_variant_job_instance_id": preferred_id,
            "preferred_variant_selection": diagnostic["preferred_variant"],
            "job_observation_id": int(active["latest_observation_id"]),
            "content_fingerprint": active["fingerprint"],
            "title": snapshot.get("title"),
            "description": snapshot.get("description"),
            "locations": snapshot.get("locations", []),
            "work_mode": snapshot.get("work_mode", "unspecified"),
            "employment_type": snapshot.get("employment_type"),
            "department": snapshot.get("department"),
            "canonical_url": active["canonical_url"],
            "market_status": state["market_status"] if state else None,
            "market_assessment": state["market_assessment"] if state else None,
            "eligibility": state["eligibility"] if state else None,
            "normal_candidate": bool(state and state["routing"]["include_in_normal_shortlist"]),
            "semantic_cache_status": cache_status,
            "semantic_assessment_id": assessed["semantic_assessment_id"] if assessed else None,
            "opportunity_assessment_id": assessed["opportunity_assessment_id"] if assessed else None,
            "base_composite_score": assessed["composite_score"] if assessed else None,
            "score": normal["score"] if normal else None,
            "tier": normal["tier"] if normal else None,
            "recommendation": normal["recommendation"] if normal else None,
            "preference_assessment": normal["preference_assessment"] if normal else None,
            "seniority_guard": normal["seniority_guard"] if normal else None,
        })
    population.sort(key=lambda item: item["cluster_id"])
    metadata = {
        "active_job_count": preflight["active_jobs"],
        "active_usable_detail_count": preflight["active_jobs_with_usable_semantic_details"],
        "unassessable_detail_count": preflight["unassessable_detail_missing_count"],
        "cluster_count": len(population),
        "normal_candidate_count": sum(item["normal_candidate"] for item in population),
        "market_status_counts": dict(Counter(item["market_status"] for item in population)),
        "cache_status_counts": dict(Counter(item["semantic_cache_status"] for item in population)),
        "latest_ingestion_run": preflight["latest_ingestion_run"],
        "source_failures_or_incomplete": preflight["source_failures_or_incomplete"],
        "candidate": preflight["candidate"],
        "semantic": preflight["semantic"],
    }
    return population, metadata


def _config_fingerprints(protocol: ProspectiveProtocol) -> dict[str, Any]:
    raw = protocol.raw
    taxonomy = load_taxonomy(raw["taxonomy_path"])
    profile = load_candidate_profile(raw["candidate_path"], taxonomy)
    experiment = load_experiment_config(raw["semantic_config_path"])
    luna = experiment.models[LUNA_TIER]
    return {
        "protocol": protocol.fingerprint,
        "candidate_full_profile": profile.full_profile_fingerprint,
        "candidate_semantic_profile": profile.semantic_profile_fingerprint,
        "candidate_scoring_preferences": profile.scoring_preference_fingerprint,
        "candidate_market_access_policy": profile.market_access_policy_fingerprint,
        "candidate_decision_preferences": profile.decision_preference_fingerprint,
        "taxonomy": _yaml_digest(raw["taxonomy_path"]),
        "market_status_rules": _yaml_digest(raw["market_rules_path"]),
        "preference_effect_policy": _yaml_digest(raw["preference_effect_policy_path"]),
        "preference_matching_rules": _yaml_digest(raw["preference_matching_rules_path"]),
        "seniority_guard_rules": load_seniority_guard_rules(raw["seniority_rules_path"]).fingerprint,
        "clustering_method_version": CLUSTERING_METHOD_VERSION,
        "preferred_variant_policy_version": PREFERRED_VARIANT_POLICY_VERSION,
        "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
        "semantic_assessor_id": ASSESSOR_ID,
        "semantic_assessor_version": f"1:{luna.model}",
        "semantic_model": luna.model,
        "reasoning_effort": luna.reasoning_effort,
    }


def _git_provenance(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True,
        ).stdout.strip()
    status = run("status", "--porcelain")
    return {
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(status),
        "worktree_status_fingerprint": _sha256_bytes(status.encode()),
    }


def render_blind_review(manifest: dict[str, Any]) -> str:
    by_id = {item["sample_item_id"]: item for item in manifest["selection"]["selected"]}
    lines = [
        f"# Prospective Phase 4 blind review — {manifest['preview_id']}", "",
        "> DIAGNOSTIC PREVIEW ONLY — not a prospective batch and not a judgment log.", "",
        "Decision diagnostics are intentionally withheld until after independent judgment.", "",
    ]
    for blind_number, sample_id in enumerate(manifest["selection"]["blind_review_order"], 1):
        item = by_id[sample_id]
        location = "; ".join(
            value.get("raw", "") for value in item.get("locations", []) if value.get("raw")
        ) or "Unspecified"
        lines.extend([
            f"## Item {blind_number:02d} — {item['company_name']} — {item['title'] or 'Title unavailable'}", "",
            f"Location: {location}", "",
            f"Work mode: {item['work_mode']}", "",
            f"Proposed preferred source: {item['canonical_url']}", "",
            f"Posting variants in proposed cluster: {item['member_count']}", "",
            "### Posting variants", "",
        ])
        for variant in item["cluster_members"]:
            variant_location = "; ".join(
                value.get("raw", "")
                for value in variant.get("locations", []) if value.get("raw")
            ) or "Unspecified"
            lines.extend([
                f"- [{variant.get('title') or 'Title unavailable'}]({variant['canonical_url']})"
                f" — {variant_location} — {variant['work_mode']}", "",
            ])
        lines.extend([
            "### Vacancy evidence", "",
            item.get("description") or "Description unavailable.", "",
            "### Independent human judgment", "",
            "- attention: YES | NO", "",
            "- application_intent: APPLY | DONT_APPLY | NEED_MORE_INFO", "",
            "- missing_information: (required when NEED_MORE_INFO)", "",
            "- market_status_human: IN_SCOPE | UNCERTAIN | OUT_OF_SCOPE", "",
            "- preferred_variant_agreement: AGREE | DISAGREE | NOT_APPLICABLE", "",
            "- cluster_correctness: CORRECT | FALSE_MERGE | NOT_APPLICABLE", "",
            "- note: (optional)", "",
        ])
    return "\n".join(lines)


def prepare_diagnostic_preview(
    database: str | Path = DEFAULT_DATABASE,
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    preview_id: str | None = None,
) -> dict[str, Any]:
    protocol = load_prospective_protocol(config_path)
    root = Path.cwd()
    population, population_metadata = build_current_cluster_population(database, protocol)
    reviewed = historical_reviewed_job_ids(protocol.raw["historical_batch_path"])
    population, exclusion = mark_historical_overlap(population, reviewed)
    selection = select_prospective_sample(population, protocol)
    reserve_items = [
        item for values in selection["reserves"].values() for item in values
    ]
    cost = observed_luna_cost(protocol.raw["roi_results_path"])
    cache = {
        "selected_sample": semantic_cache_preflight(
            selection["selected"], cost["estimated_cost_per_cache_miss_usd"],
        ),
        "frozen_reserves": semantic_cache_preflight(
            reserve_items, cost["estimated_cost_per_cache_miss_usd"],
        ),
        "full_current_population": semantic_cache_preflight(
            population, cost["estimated_cost_per_cache_miss_usd"],
        ),
    }
    preview_id = preview_id or (
        "phase4-prospective-preview-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
        + uuid.uuid4().hex[:8]
    )
    frozen = _config_fingerprints(protocol)
    manifest = {
        "schema_version": 1,
        "artifact_type": ARTIFACT_TYPE,
        "is_prospective_batch": False,
        "preview_id": preview_id,
        "experiment_id": protocol.experiment_id,
        "protocol_version": protocol.version,
        "protocol": protocol.raw,
        "created_at": utc_now(),
        "external_calls_made": 0,
        "human_judgments_present": False,
        "batch_creation_authorized": False,
        "sampling_ready_after_cache_preflight": (
            cache["full_current_population"]["semantic_assessment_required_misses"] == 0
        ),
        "warning": "Read-only diagnostic preview from pre-existing state. It is not the future prospective batch.",
        "population": population,
        "population_summary": population_metadata,
        "historical_exclusion": exclusion,
        "selection": selection,
        "semantic_preflight": cache,
        "frozen_configuration": frozen,
        "provenance": {
            "git": _git_provenance(root),
            "database_path": str(database),
            "database_sha256": _sha256_file(database),
            "historical_batch_path": protocol.raw["historical_batch_path"],
            "historical_batch_sha256": _sha256_file(protocol.raw["historical_batch_path"]),
            "protocol_path": str(config_path),
            "protocol_sha256": _sha256_file(config_path),
        },
    }
    directory = Path(output_root) / preview_id
    directory.mkdir(parents=True, exist_ok=False)
    detailed_path = directory / "preview.json"
    detailed_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    detailed_path.write_text(detailed_text, encoding="utf-8")
    blind_path = directory / "blind_review.md"
    blind_path.write_text(render_blind_review(manifest), encoding="utf-8")
    public_population = {
        key: value for key, value in population_metadata.items()
        if key not in {"candidate", "semantic"}
    }
    aggregate = {
        "schema_version": 1,
        "artifact_type": ARTIFACT_TYPE,
        "is_prospective_batch": False,
        "preview_id": preview_id,
        "experiment_id": protocol.experiment_id,
        "protocol_version": protocol.version,
        "created_at": manifest["created_at"],
        "warning": manifest["warning"],
        "human_judgments_present": False,
        "batch_creation_authorized": False,
        "sampling_ready_after_cache_preflight": manifest["sampling_ready_after_cache_preflight"],
        "external_calls_made": 0,
        "population": public_population,
        "historical_exclusion": exclusion,
        "sample": {
            "target": protocol.sampling["target"],
            "selected_count": len(selection["selected"]),
            "stratum_counts": selection["stratum_counts"],
            "shortfalls": selection["shortfalls"],
            "reserve_counts": {key: len(value) for key, value in selection["reserves"].items()},
            "employer_counts_normal": selection["employer_counts_normal"],
            "employer_counts_market_controls": selection["employer_counts_market_controls"],
            "cap_relaxations": selection["cap_relaxations"],
        },
        "semantic_preflight": cache,
        "frozen_configuration": frozen,
        "provenance": {
            **manifest["provenance"],
            "private_preview_sha256": _sha256_bytes(detailed_text.encode()),
            "private_blind_review_sha256": _sha256_file(blind_path),
        },
        "limitations": [
            "The preview uses existing local state and is not the fresh prospective batch.",
            "No human judgments were collected and no prospective verdict was computed.",
            "Detailed candidate-derived opportunity evidence remains private/local.",
        ],
    }
    aggregate_path = directory / "aggregate_summary.json"
    aggregate_path.write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return {
        "preview_id": preview_id,
        "aggregate_summary_path": str(aggregate_path),
        "private_preview_path": str(detailed_path),
        "private_blind_review_path": str(blind_path),
        "summary": aggregate,
    }


def _judgment_by_cluster(judgments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in judgments:
        cluster_id = item.get("cluster_id")
        if cluster_id:
            result[cluster_id] = item
    return result


def calculate_prospective_metrics(
    prepared_manifest: dict[str, Any], judgments: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate predeclared metrics. This function never alters the manifest."""
    protocol = prepared_manifest["protocol"]
    labels = protocol["human_labels"]
    metrics_config = protocol["metrics"]
    normal_strata = set(metrics_config["normal_strata"])
    attention_recommendations = set(metrics_config["system_attention_recommendations"])
    by_cluster = _judgment_by_cluster(judgments)
    reviewed = []
    for item in prepared_manifest["selection"]["selected"]:
        judgment = by_cluster.get(item["cluster_id"])
        if not judgment or judgment.get("review_status", "COMPLETED") != "COMPLETED":
            continue
        for field, allowed in labels.items():
            if judgment.get(field) not in allowed:
                raise ProspectiveValidationError(f"invalid {field} for {item['cluster_id']}")
        if judgment["application_intent"] == "NEED_MORE_INFO" and not judgment.get("missing_information"):
            raise ProspectiveValidationError("NEED_MORE_INFO requires missing_information")
        reviewed.append((item, judgment))
    normal = [(i, j) for i, j in reviewed if i["stratum"] in normal_strata]
    top = [(i, j) for i, j in reviewed if i["stratum"] == "TOP_ATTENTION"]
    human_apply = [(i, j) for i, j in normal if j["application_intent"] == "APPLY"]
    terminal_apply = [(i, j) for i, j in normal if i["recommendation"] == "APPLY"]
    market = [(i, j) for i, j in reviewed if j["market_status_human"] in labels["market_status_human"]]
    variant = [
        (i, j) for i, j in reviewed
        if j["preferred_variant_agreement"] in {"AGREE", "DISAGREE"}
    ]
    multi = [(i, j) for i, j in reviewed if i["member_count"] > 1]
    system_attention = lambda item: item["recommendation"] in attention_recommendations
    ratio = lambda numerator, denominator: numerator / denominator if denominator else None
    return {
        "reviewed": len(reviewed),
        "sample_size": len(prepared_manifest["selection"]["selected"]),
        "human_apply_attention_recall": ratio(
            sum(system_attention(i) for i, _ in human_apply), len(human_apply),
        ),
        "top_attention_acceptance": ratio(
            sum(j["attention"] == "YES" for _, j in top), len(top),
        ),
        "ranking_agreement": ratio(
            sum(system_attention(i) == (j["attention"] == "YES") for i, j in normal),
            len(normal),
        ),
        "terminal_apply_acceptance": ratio(
            sum(j["application_intent"] == "APPLY" for _, j in terminal_apply),
            len(terminal_apply),
        ),
        "market_status_exact_agreement": ratio(
            sum(i["market_status"] == j["market_status_human"] for i, j in market),
            len(market),
        ),
        "preferred_variant_agreement": ratio(
            sum(j["preferred_variant_agreement"] == "AGREE" for _, j in variant),
            len(variant),
        ),
        "confirmed_false_merge_count": sum(
            j["cluster_correctness"] == "FALSE_MERGE" for _, j in multi
        ),
        "need_more_info_count": sum(
            j["application_intent"] == "NEED_MORE_INFO" for _, j in reviewed
        ),
        "market_controls_excluded_from_normal_metrics": sum(
            item["stratum"] == "MARKET_CONTROL"
            for item in prepared_manifest["selection"]["selected"]
        ),
    }


def stopping_status(
    prepared_manifest: dict[str, Any], judgments: list[dict[str, Any]],
) -> dict[str, Any]:
    target = int(prepared_manifest["protocol"]["stopping"]["completed_cluster_judgments"])
    selected_ids = {item["cluster_id"] for item in prepared_manifest["selection"]["selected"]}
    current = _judgment_by_cluster(judgments)
    completed = sum(
        current.get(cluster_id, {}).get("review_status", "COMPLETED") == "COMPLETED"
        for cluster_id in selected_ids if cluster_id in current
    )
    unavailable = sum(
        current.get(cluster_id, {}).get("review_status") == "UNAVAILABLE"
        for cluster_id in selected_ids
    )
    effective_target = min(target, len(selected_ids))
    return {
        "target": effective_target,
        "completed": completed,
        "unavailable": unavailable,
        "complete": completed == effective_target,
        "early_stopping_allowed": False,
        "unavailable_is_automatic_ranking_disagreement": False,
        "replacement_policy": "FROZEN_RESERVE_SAME_STRATUM_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a read-only diagnostic preview of Phase 4 prospective validation",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-protocol")
    preview = sub.add_parser("preview")
    preview.add_argument("--preview-id")
    args = parser.parse_args()
    if args.command == "validate-protocol":
        protocol = load_prospective_protocol(args.config)
        print(json.dumps({
            "experiment_id": protocol.experiment_id,
            "protocol_version": protocol.version,
            "protocol_fingerprint": protocol.fingerprint,
            "valid": True,
        }, indent=2))
        return 0
    result = prepare_diagnostic_preview(
        args.database, args.config, args.output_root, args.preview_id,
    )
    print(json.dumps({
        "preview_id": result["preview_id"],
        "aggregate_summary_path": result["aggregate_summary_path"],
        "private_preview_path": result["private_preview_path"],
        "private_blind_review_path": result["private_blind_review_path"],
        "sample": result["summary"]["sample"],
        "semantic_preflight": result["summary"]["semantic_preflight"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
