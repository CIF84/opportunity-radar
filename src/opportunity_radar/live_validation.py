from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opportunity_radar.config import load_companies
from opportunity_radar.eligibility import evaluate_eligibility
from opportunity_radar.experimental_semantic import ExperimentalSemanticAssessor, OpenAIResponsesTransport
from opportunity_radar.market_routing import (
    assess_routed_opportunity,
    compose_market_routing,
)
from opportunity_radar.market_status import (
    CurrentCandidateMarketStatus,
    evaluate_current_candidate_market,
    load_market_normalization_rules,
)
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import EligibilityStatus, Recommendation, SemanticJobInput
from opportunity_radar.phase3_repository import Phase3Repository
from opportunity_radar.roi_experiment import load_experiment_config
from opportunity_radar.scoring import rank_tier
from opportunity_radar.semantic import SEMANTIC_CONTRACT_VERSION
from opportunity_radar.state_repository import StateRepository


LUNA_TIER = "economical"
ASSESSOR_ID = "external-structured"
DISAGREEMENT_CATEGORIES = {
    "SEMANTIC_INTERPRETATION_ERROR",
    "CANDIDATE_PROFILE_MISSING_INFORMATION",
    "CANDIDATE_PROFILE_INACCURATE",
    "JOB_EVIDENCE_INSUFFICIENT",
    "DETERMINISTIC_ELIGIBILITY_ISSUE",
    "SCORING_WEIGHT_OR_CALIBRATION",
    "UNREPRESENTED_HUMAN_PREFERENCE",
    "EXTERNAL_PRIVATE_INFORMATION",
    "BENCHMARK_OR_TAXONOMY_LIMITATION",
    "OTHER",
}
HUMAN_DECISIONS = {"APPLY", "REVIEW", "DONT_APPLY"}
TIERS = {"TOP", "HIGH", "REVIEW", "LOW"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _readonly_connection(path: str | Path) -> sqlite3.Connection:
    uri = f"file:{Path(path).resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _semantic_job(snapshot: dict[str, Any]) -> SemanticJobInput:
    return SemanticJobInput(
        snapshot["company_name"], snapshot.get("title"), snapshot.get("description") or "",
        tuple(snapshot.get("locations", [])), snapshot.get("work_mode", "unspecified"),
        snapshot.get("employment_type"), snapshot.get("department"),
    )


def _active_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT ji.job_instance_id,ji.company_id,ji.canonical_url,ji.current_fingerprint,
                  ji.latest_observation_id,jo.fingerprint,jo.normalized_snapshot,jo.run_id
           FROM job_instances ji LEFT JOIN job_observations jo
             ON jo.job_observation_id=ji.latest_observation_id
           WHERE ji.lifecycle_state='ACTIVE' ORDER BY ji.job_instance_id"""
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["snapshot"] = json.loads(item["normalized_snapshot"]) if item["normalized_snapshot"] else None
        except json.JSONDecodeError:
            item["snapshot"] = None
        result.append(item)
    return result


def _usable(row: dict[str, Any]) -> bool:
    snapshot = row.get("snapshot")
    return bool(snapshot and snapshot.get("title") and (snapshot.get("description") or "").strip())


def _cache_hit(connection: sqlite3.Connection, row: dict[str, Any], profile, assessor_version: str) -> bool:
    try:
        found = connection.execute(
            """SELECT 1 FROM semantic_assessments
               WHERE job_instance_id=? AND content_fingerprint=?
                 AND semantic_profile_fingerprint=? AND semantic_contract_version=?
                 AND assessor_id=? AND assessor_version=? LIMIT 1""",
            (row["job_instance_id"], row["fingerprint"], profile.semantic_profile_fingerprint,
             SEMANTIC_CONTRACT_VERSION, ASSESSOR_ID, assessor_version),
        ).fetchone()
        return found is not None
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return False
        raise


def observed_luna_cost(path: str | Path = "output/semantic_roi_experiment.json") -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    luna = raw["semantic_models"][LUNA_TIER]
    usage = luna.get("usage_records", [])
    if not usage:
        raise ValueError("completed Luna usage records are required for live-validation estimates")
    repetitions = int(luna.get("stability", {}).get("repetitions") or 1)
    first_count = len(usage) // repetitions
    first = usage[:first_count]
    first_cost = sum(float(item["estimated_cost_usd"]) for item in first)
    return {
        "source": str(path),
        "observed_calls": len(usage),
        "first_assessment_sample_size": len(first),
        "first_assessment_total_cost_usd": round(first_cost, 8),
        "estimated_cost_per_cache_miss_usd": round(first_cost / len(first), 8),
    }


def build_preflight(
    database: str | Path,
    companies_path: str | Path = "config/companies.yaml",
    candidate_path: str | Path = "config/candidate.yaml",
    taxonomy_path: str | Path = "config/taxonomy.yaml",
    semantic_config_path: str | Path = "config/semantic_experiment.yaml",
    roi_results_path: str | Path = "output/semantic_roi_experiment.json",
    market_rules_path: str | Path = "config/market_status_rules.yaml",
) -> dict[str, Any]:
    configs = load_companies(companies_path)
    taxonomy = load_taxonomy(taxonomy_path)
    profile = load_candidate_profile(candidate_path, taxonomy)
    market_rules = load_market_normalization_rules(market_rules_path)
    experiment = load_experiment_config(semantic_config_path)
    luna = experiment.models[LUNA_TIER]
    assessor_version = f"1:{luna.model}"
    cost = observed_luna_cost(roi_results_path)
    with _readonly_connection(database) as connection:
        active = _active_rows(connection)
        assessable, missing = [], []
        counts = Counter()
        market_counts = Counter()
        hits = misses = 0
        out_of_scope_existing_hits = 0
        semantic_processing_count = 0
        for row in active:
            if not _usable(row):
                missing.append({"job_instance_id": row["job_instance_id"], "company_id": row["company_id"], "classification": "UNASSESSABLE_DETAIL_MISSING"})
                continue
            job = _semantic_job(row["snapshot"])
            eligibility = evaluate_eligibility(job, profile).status.value
            counts[eligibility] += 1
            market = evaluate_current_candidate_market(job, profile, market_rules)
            market_counts[market.status.value] += 1
            routing = compose_market_routing(
                market.status, EligibilityStatus(eligibility),
            )
            existing_hit = _cache_hit(connection, row, profile, assessor_version)
            hit = routing.eligible_for_semantic_processing and existing_hit
            if routing.eligible_for_semantic_processing:
                semantic_processing_count += 1
                hits += int(hit); misses += int(not hit)
            elif market.status is CurrentCandidateMarketStatus.OUT_OF_SCOPE:
                out_of_scope_existing_hits += int(existing_hit)
            assessable.append({
                "job_instance_id": row["job_instance_id"],
                "job_observation_id": row["latest_observation_id"],
                "content_fingerprint": row["fingerprint"],
                "company_id": row["company_id"],
                "eligibility": eligibility,
                "market_status": market.status.value,
                "market_assessment": market.payload(),
                "routing": routing.payload(),
                "eligible_for_semantic_processing": routing.eligible_for_semantic_processing,
                "compatible_luna_cache_hit": hit,
                "existing_semantic_cache_hit": existing_hit,
            })
        latest_run = connection.execute("SELECT * FROM ingestion_runs ORDER BY started_at DESC LIMIT 1").fetchone()
        sources = []
        event_counts: dict[str, int] = {}
        if latest_run:
            sources = [dict(row) for row in connection.execute("SELECT * FROM source_observations WHERE run_id=? ORDER BY company_id", (latest_run["run_id"],)).fetchall()]
            event_counts = dict(Counter(row["event_type"] for row in connection.execute("SELECT event_type FROM events WHERE run_id=?", (latest_run["run_id"],)).fetchall()))
    incomplete = [
        {"company_id": item["company_id"], "status": item["status"], "inventory_complete": bool(item["inventory_complete"]), "details_complete": bool(item["details_complete"]), "error_type": item["error_type"], "error_message": item["error_message"]}
        for item in sources if item["status"] != "SUCCESS" or not item["inventory_complete"] or not item["details_complete"]
    ]
    return {
        "generated_at": utc_now(),
        "read_only": True,
        "configured_employers": len(configs),
        "configured_company_ids": [item.company_id for item in configs],
        "latest_ingestion_run": dict(latest_run) if latest_run else None,
        "source_observations_in_latest_run": len(sources),
        "source_failures_or_incomplete": incomplete,
        "active_jobs": len(active),
        "active_jobs_with_usable_semantic_details": len(assessable),
        "unassessable_detail_missing_count": len(missing),
        "unassessable_detail_missing": missing,
        "eligibility": {key: counts.get(key, 0) for key in ("ELIGIBLE", "UNCERTAIN", "INELIGIBLE")},
        "market_status": {
            key: market_counts.get(key, 0)
            for key in ("IN_SCOPE", "UNCERTAIN", "OUT_OF_SCOPE")
        },
        "jobs_eligible_for_semantic_processing": semantic_processing_count,
        "compatible_luna_cache_hits": hits,
        "out_of_scope_existing_cache_hits": out_of_scope_existing_hits,
        "luna_cache_misses": misses,
        "expected_external_calls": misses,
        "estimated_semantic_cost_usd": round(misses * cost["estimated_cost_per_cache_miss_usd"], 6),
        "cost_assumption": cost,
        "candidate": {"profile_id": profile.profile_id, "version": profile.version, "semantic_profile_fingerprint": profile.semantic_profile_fingerprint, "scoring_preference_fingerprint": profile.scoring_preference_fingerprint, "market_access_policy_fingerprint": profile.market_access_policy_fingerprint},
        "semantic": {"model": luna.model, "reasoning_effort": luna.reasoning_effort, "contract_version": SEMANTIC_CONTRACT_VERSION, "assessor_id": ASSESSOR_ID, "assessor_version": assessor_version},
        "latest_run_event_counts": event_counts,
        "assessable_jobs": assessable,
        "note": "OUT_OF_SCOPE jobs are excluded before semantic calls; other hard-eligible/uncertain cache misses are assessed before sampling.",
    }


def _write_immutable(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(value)


def _current_assessment(connection: sqlite3.Connection, row: dict[str, Any], profile, assessor_version: str):
    return connection.execute(
        """SELECT oa.opportunity_assessment_id,sa.semantic_assessment_id
           FROM opportunity_assessments oa
           JOIN candidate_profiles cp ON cp.candidate_profile_row_id=oa.candidate_profile_row_id
           JOIN semantic_assessments sa ON sa.semantic_assessment_id=oa.semantic_assessment_id
           WHERE oa.job_instance_id=? AND oa.job_observation_id=?
             AND cp.full_profile_fingerprint=? AND oa.scoring_preference_fingerprint=?
             AND sa.content_fingerprint=? AND sa.semantic_contract_version=?
             AND sa.assessor_id=? AND sa.assessor_version=?
           ORDER BY oa.opportunity_assessment_id DESC LIMIT 1""",
        (row["job_instance_id"], row["latest_observation_id"], profile.full_profile_fingerprint,
         profile.scoring_preference_fingerprint, row["fingerprint"], SEMANTIC_CONTRACT_VERSION,
         ASSESSOR_ID, assessor_version),
    ).fetchone()


def run_luna_assessment(
    database: str | Path,
    output_root: str | Path = "output/live_validation",
    companies_path: str | Path = "config/companies.yaml",
    candidate_path: str | Path = "config/candidate.yaml",
    taxonomy_path: str | Path = "config/taxonomy.yaml",
    semantic_config_path: str | Path = "config/semantic_experiment.yaml",
    roi_results_path: str | Path = "output/semantic_roi_experiment.json",
    run_id: str | None = None,
    market_rules_path: str | Path = "config/market_status_rules.yaml",
) -> dict[str, Any]:
    preflight = build_preflight(
        database, companies_path, candidate_path, taxonomy_path,
        semantic_config_path, roi_results_path, market_rules_path,
    )
    taxonomy = load_taxonomy(taxonomy_path)
    profile = load_candidate_profile(candidate_path, taxonomy)
    market_rules = load_market_normalization_rules(market_rules_path)
    experiment = load_experiment_config(semantic_config_path)
    luna = experiment.models[LUNA_TIER]
    transport = OpenAIResponsesTransport(experiment.endpoint, experiment.api_key_env, experiment.connect_timeout, experiment.read_timeout)
    assessor = ExperimentalSemanticAssessor(taxonomy, luna, transport)
    state = StateRepository(database)
    phase3 = Phase3Repository(state)
    run_id = run_id or f"live-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    records = []
    with state.connect() as connection:
        rows = {row["job_instance_id"]: row for row in _active_rows(connection)}
    eligible = [
        item for item in preflight["assessable_jobs"]
        if item["eligible_for_semantic_processing"]
    ]
    for index, item in enumerate(eligible, 1):
        row = rows[item["job_instance_id"]]
        before = len(assessor.calls)
        print(f"[{index}/{len(eligible)}] START job_instance_id={row['job_instance_id']} company={row['company_id']} cache={'hit' if item['compatible_luna_cache_hit'] else 'miss'}", flush=True)
        try:
            routed = assess_routed_opportunity(
                _semantic_job(row["snapshot"]), profile, taxonomy, assessor,
                market_rules,
                repository=phase3, job_instance_id=row["job_instance_id"],
                job_observation_id=row["latest_observation_id"], content_fingerprint=row["fingerprint"],
            )
            result = routed.opportunity
            if result is None:
                raise AssertionError("semantic-processing route returned no opportunity assessment")
            usage = assessor.calls[-1] if len(assessor.calls) > before else None
            with state.connect() as connection:
                ids = _current_assessment(connection, row, profile, assessor.assessor_version)
            record = {
                "job_instance_id": row["job_instance_id"], "job_observation_id": row["latest_observation_id"],
                "content_fingerprint": row["fingerprint"], "company_id": row["company_id"],
                "eligibility": item["eligibility"], "market_status": routed.market.status.value,
                "market_assessment": routed.market.payload(), "routing": routed.routing.payload(),
                "recommendation": result.recommendation.value,
                "cache_hit": result.semantic_reused,
                "semantic_assessment_id": ids["semantic_assessment_id"],
                "opportunity_assessment_id": ids["opportunity_assessment_id"],
                "model": luna.model, "usage": asdict(usage) if usage else None, "error": None,
            }
            print(f"[{index}/{len(eligible)}] SUCCESS cache_reused={result.semantic_reused} cost_usd={(usage.estimated_cost_usd if usage else 0):.8f}", flush=True)
        except Exception as exc:
            usage = assessor.calls[-1] if len(assessor.calls) > before else None
            record = {
                "job_instance_id": row["job_instance_id"], "job_observation_id": row["latest_observation_id"],
                "content_fingerprint": row["fingerprint"], "company_id": row["company_id"],
                "eligibility": item["eligibility"], "market_status": item["market_status"],
                "market_assessment": item["market_assessment"], "routing": item["routing"],
                "recommendation": None, "cache_hit": False,
                "semantic_assessment_id": None, "opportunity_assessment_id": None,
                "model": luna.model, "usage": asdict(usage) if usage else None,
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(f"[{index}/{len(eligible)}] ERROR {record['error']}", flush=True)
        records.append(record)
    calls = [record["usage"] for record in records if record["usage"]]
    manifest = {
        "validation_run_id": run_id, "created_at": utc_now(), "preflight": preflight,
        "candidate": preflight["candidate"], "semantic": preflight["semantic"], "jobs": records,
        "summary": {
            "jobs_processed": len(records), "cache_hits": sum(record["cache_hit"] for record in records),
            "external_calls": sum(bool(record["usage"]) for record in records),
            "failures": sum(bool(record["error"]) for record in records),
            "input_tokens": sum(item["input_tokens"] for item in calls),
            "cached_input_tokens": sum(item["cached_input_tokens"] for item in calls),
            "output_tokens": sum(item["output_tokens"] for item in calls),
            "reasoning_tokens": sum(item["reasoning_tokens"] for item in calls),
            "actual_cost_usd": round(sum(item["estimated_cost_usd"] for item in calls), 8),
            "mean_latency_seconds": (sum(item["latency_seconds"] for item in calls) / len(calls)) if calls else None,
        },
    }
    path = Path(output_root) / "runs" / f"{run_id}.json"
    _write_immutable(path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    manifest["manifest_path"] = str(path)
    return manifest


def _assessed_pool(
    database: str | Path,
    profile,
    assessor_version: str,
    market_rules,
) -> list[dict[str, Any]]:
    with _readonly_connection(database) as connection:
        rows = connection.execute(
            """SELECT ji.job_instance_id,ji.company_id,ji.canonical_url,ji.latest_observation_id,
                      jo.fingerprint,jo.normalized_snapshot,jo.run_id,
                      oa.opportunity_assessment_id,oa.composite_score,oa.recommendation,oa.eligibility_json,
                      sa.semantic_assessment_id,sa.assessment_json
               FROM job_instances ji JOIN job_observations jo ON jo.job_observation_id=ji.latest_observation_id
               JOIN opportunity_assessments oa ON oa.job_instance_id=ji.job_instance_id AND oa.job_observation_id=jo.job_observation_id
               JOIN candidate_profiles cp ON cp.candidate_profile_row_id=oa.candidate_profile_row_id
               JOIN semantic_assessments sa ON sa.semantic_assessment_id=oa.semantic_assessment_id
               WHERE ji.lifecycle_state='ACTIVE' AND cp.full_profile_fingerprint=?
                 AND oa.scoring_preference_fingerprint=? AND sa.content_fingerprint=jo.fingerprint
                 AND sa.semantic_contract_version=? AND sa.assessor_id=? AND sa.assessor_version=?
               ORDER BY oa.opportunity_assessment_id DESC""",
            (profile.full_profile_fingerprint, profile.scoring_preference_fingerprint,
             SEMANTIC_CONTRACT_VERSION, ASSESSOR_ID, assessor_version),
        ).fetchall()
    seen = set(); pool = []
    for raw in rows:
        if raw["job_instance_id"] in seen:
            continue
        seen.add(raw["job_instance_id"])
        snapshot = json.loads(raw["normalized_snapshot"])
        eligibility = json.loads(raw["eligibility_json"])["status"]
        job = _semantic_job(snapshot)
        market = evaluate_current_candidate_market(job, profile, market_rules)
        routing = compose_market_routing(
            market.status,
            EligibilityStatus(eligibility),
            Recommendation(raw["recommendation"]),
        )
        if not routing.include_in_normal_shortlist:
            continue
        semantic = json.loads(raw["assessment_json"])
        pool.append({
            "job_instance_id": raw["job_instance_id"], "job_observation_id": raw["latest_observation_id"],
            "content_fingerprint": raw["fingerprint"], "opportunity_assessment_id": raw["opportunity_assessment_id"],
            "semantic_assessment_id": raw["semantic_assessment_id"], "company_id": raw["company_id"],
            "company_name": snapshot["company_name"], "title": snapshot["title"], "locations": snapshot.get("locations", []),
            "work_mode": snapshot.get("work_mode", "unspecified"), "canonical_url": raw["canonical_url"],
            "score": raw["composite_score"], "tier": rank_tier(raw["composite_score"]),
            "recommendation": routing.recommendation.value,
            "recommendation_before_market_policy": raw["recommendation"],
            "market_status": market.status.value,
            "market_assessment": market.payload(),
            "market_routing": routing.payload(),
            "eligibility": eligibility,
            "source_run_id": raw["run_id"], "semantic": semantic,
        })
    return sorted(pool, key=lambda item: (-(item["score"] if item["score"] is not None else -1), item["job_instance_id"]))


def select_validation_sample(pool: list[dict[str, Any]], seed: str, target: int = 30) -> list[dict[str, Any]]:
    ranked = [dict(item, rank=index + 1) for index, item in enumerate(pool)]
    n = min(target, len(ranked))
    if n == 0:
        return []
    if n >= 30:
        low_n, marginal_n = 5, 5
    elif n >= 3:
        low_n = min(5, max(1, n // 6))
        marginal_n = min(5, max(1, n // 6))
    else:
        low_n = marginal_n = 0
    top_n = n - low_n - marginal_n
    chosen: list[dict[str, Any]] = []
    low = ranked[-low_n:] if low_n else []
    low_ids = {item["job_instance_id"] for item in low}
    remaining = [item for item in ranked if item["job_instance_id"] not in low_ids]
    top = remaining[:top_n]
    top_ids = {item["job_instance_id"] for item in top}
    candidates = [item for item in remaining if item["job_instance_id"] not in top_ids]
    candidates.sort(key=lambda item: (
        -(item["score"] if item["score"] is not None else -1),
        hashlib.sha256(f"{seed}:{item['job_instance_id']}".encode()).hexdigest(),
    ))
    marginal = candidates[:marginal_n]
    for stratum, items in (("TOP_RANKED", top), ("MARGINAL_BELOW_CUTOFF", marginal), ("LOW_CONTROL", low)):
        chosen.extend(dict(item, stratum=stratum) for item in items)
    chosen.sort(key=lambda item: item["rank"])
    return [dict(item, review_number=index + 1) for index, item in enumerate(chosen)]


def _importance_order(value: str) -> int:
    return {"VERY_HIGH": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(value, 4)


def render_review(batch: dict[str, Any]) -> str:
    lines = [f"# Live Decision Validation — {batch['validation_batch_id']}", "", f"Pool: {batch['ranked_pool_size']} · Review sample: {len(batch['selected_jobs'])}", "", "Record judgments with `opportunity-radar-live-validation record ...`; this report is not the judgment source of truth.", ""]
    headings = (("TOP_RANKED", "TOP-RANKED"), ("MARGINAL_BELOW_CUTOFF", "MARGINAL / BELOW CUTOFF"), ("LOW_CONTROL", "LOW CONTROLS"))
    for key, heading in headings:
        lines.extend([f"## {heading}", ""])
        for item in (job for job in batch["selected_jobs"] if job["stratum"] == key):
            semantic = item["semantic"]
            dimensions = semantic["dimensions"]
            reason = dimensions.get("functional_alignment", {}).get("reason") or next((value.get("reason") for value in dimensions.values() if value.get("reason")), "No concise reason available.")
            strengths = sorted(semantic.get("strengths", []), key=lambda x: _importance_order(x.get("importance", "")))[:3]
            gaps_risks = sorted(semantic.get("gaps", []) + semantic.get("risks", []), key=lambda x: _importance_order(x.get("importance", "")))[:3]
            location = "; ".join(loc.get("raw", "") for loc in item["locations"] if loc.get("raw")) or "Unspecified"
            lines.extend([
                f"### {item['review_number']}. Rank {item['rank']} — {item['company_name']} — {item['title']}", "",
                f"{location} · {item['work_mode']} · [job source]({item['canonical_url']})", "",
                f"**RADAR {item['score']:.2f} · {item['tier']} · {item['recommendation']} · market {item.get('market_status', 'NOT_RECORDED')} · eligibility {item['eligibility']}**" if item["score"] is not None else f"**RADAR unavailable · {item['tier']} · {item['recommendation']} · market {item.get('market_status', 'NOT_RECORDED')} · eligibility {item['eligibility']}**", "",
                f"Why: {reason}", "",
                "Strengths: " + ("; ".join(x["statement"] for x in strengths) if strengths else "None recorded."), "",
                "Gaps / risks: " + ("; ".join(x["statement"] for x in gaps_risks) if gaps_risks else "None recorded."), "",
                "Human review: APPLY / REVIEW / DONT_APPLY · ranking agree/disagree", "",
            ])
    uncertain = [job for job in batch["selected_jobs"] if job["eligibility"] == "UNCERTAIN"]
    if uncertain:
        lines.extend(["## UNCERTAIN ELIGIBILITY", "", "Review numbers: " + ", ".join(str(job["review_number"]) for job in uncertain), ""])
    market_uncertain = [
        job for job in batch["selected_jobs"] if job.get("market_status") == "UNCERTAIN"
    ]
    if market_uncertain:
        lines.extend([
            "## UNCERTAIN MARKET ACCESS", "",
            "Review numbers: " + ", ".join(
                str(job["review_number"]) for job in market_uncertain
            ), "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def prepare_batch(
    database: str | Path,
    output_root: str | Path = "output/live_validation",
    candidate_path: str | Path = "config/candidate.yaml",
    taxonomy_path: str | Path = "config/taxonomy.yaml",
    semantic_config_path: str | Path = "config/semantic_experiment.yaml",
    companies_path: str | Path = "config/companies.yaml",
    roi_results_path: str | Path = "output/semantic_roi_experiment.json",
    batch_id: str | None = None,
    seed: str | None = None,
    usage_run_path: str | Path | None = None,
    market_rules_path: str | Path = "config/market_status_rules.yaml",
) -> dict[str, Any]:
    taxonomy = load_taxonomy(taxonomy_path); profile = load_candidate_profile(candidate_path, taxonomy)
    market_rules = load_market_normalization_rules(market_rules_path)
    experiment = load_experiment_config(semantic_config_path); luna = experiment.models[LUNA_TIER]
    pool = _assessed_pool(database, profile, f"1:{luna.model}", market_rules)
    if not pool:
        raise ValueError("no compatible assessed active jobs; run explicit Luna assessment first")
    batch_id = batch_id or f"batch-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    seed = seed or batch_id
    selected = select_validation_sample(pool, seed)
    preflight = build_preflight(
        database, companies_path, candidate_path, taxonomy_path,
        semantic_config_path, roi_results_path, market_rules_path,
    )
    usage = json.loads(Path(usage_run_path).read_text()) if usage_run_path else None
    batch = {
        "validation_batch_id": batch_id, "created_at": utc_now(), "sample_seed": seed,
        "ranked_pool_size": len(pool), "selected_jobs": selected,
        "candidate": {"profile_id": profile.profile_id, "version": profile.version, "full_profile_fingerprint": profile.full_profile_fingerprint, "semantic_profile_fingerprint": profile.semantic_profile_fingerprint, "scoring_preference_fingerprint": profile.scoring_preference_fingerprint, "market_access_policy_fingerprint": profile.market_access_policy_fingerprint},
        "semantic": {"model": luna.model, "reasoning_effort": luna.reasoning_effort, "assessor_id": ASSESSOR_ID, "assessor_version": f"1:{luna.model}", "contract_version": SEMANTIC_CONTRACT_VERSION},
        "preflight_snapshot": preflight, "usage_run": usage,
        "sampling": {"target": 30, "strata": dict(Counter(item["stratum"] for item in selected))},
        "limitations": "Stratified reviewed sample; aggregate agreement is not an unbiased market estimate.",
    }
    directory = Path(output_root) / batch_id
    directory.mkdir(parents=True, exist_ok=False)
    _write_immutable(directory / "batch.json", json.dumps(batch, ensure_ascii=False, indent=2) + "\n")
    _write_immutable(directory / "review.md", render_review(batch))
    batch["batch_path"] = str(directory / "batch.json")
    batch["review_path"] = str(directory / "review.md")
    return batch


def load_batch(output_root: str | Path, batch_id: str) -> dict[str, Any]:
    return json.loads((Path(output_root) / batch_id / "batch.json").read_text(encoding="utf-8"))


def load_judgments(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.exists():
        return []
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]


def current_judgments(records: list[dict[str, Any]], batch_id: str | None = None) -> dict[tuple[str, int], dict[str, Any]]:
    relevant = [item for item in records if batch_id is None or item["validation_batch_id"] == batch_id]
    by_id = {item["judgment_id"]: item for item in relevant}
    superseded = set()
    for item in relevant:
        previous = item.get("supersedes_judgment_id")
        if previous:
            if previous not in by_id:
                raise ValueError(f"superseded judgment not found: {previous}")
            old = by_id[previous]
            if (old["validation_batch_id"], old["job_instance_id"]) != (item["validation_batch_id"], item["job_instance_id"]):
                raise ValueError("judgment may supersede only the same batch/job")
            if previous in superseded:
                raise ValueError("judgment supersession cannot branch")
            superseded.add(previous)
    return {(item["validation_batch_id"], item["job_instance_id"]): item for item in relevant if item["judgment_id"] not in superseded}


def resolve_batch_job(
    batch: dict[str, Any], job_or_review_id: str | None = None, *,
    review_number: int | None = None, job_instance_id: int | None = None,
) -> dict[str, Any]:
    """Resolve an explicit identity, or reject ambiguous legacy positional IDs."""
    modes = sum(value is not None for value in (job_or_review_id, review_number, job_instance_id))
    if modes != 1:
        raise ValueError("specify exactly one of positional id, --review-number, or --job-instance-id")
    jobs = batch["selected_jobs"]
    if review_number is not None:
        matches = [item for item in jobs if item["review_number"] == review_number]
        label = f"review number {review_number}"
    elif job_instance_id is not None:
        matches = [item for item in jobs if item["job_instance_id"] == job_instance_id]
        label = f"job instance id {job_instance_id}"
    else:
        matches = [
            item for item in jobs
            if str(item["review_number"]) == str(job_or_review_id)
            or str(item["job_instance_id"]) == str(job_or_review_id)
        ]
        unique = {item["job_instance_id"]: item for item in matches}
        matches = list(unique.values())
        label = f"legacy positional id {job_or_review_id}"
        if len(matches) > 1:
            raise ValueError(
                f"ambiguous {label}; use --review-number or --job-instance-id"
            )
    if not matches:
        raise ValueError(f"job not found in batch for {label}")
    if len(matches) != 1:
        raise ValueError(f"{label} is not unique in batch")
    return matches[0]


def append_judgment(
    batch: dict[str, Any], judgments_path: str | Path, job_or_review_id: str | None, decision: str,
    ranking_agreement: bool, expected_tier: str | None = None, note: str | None = None,
    categories: list[str] | None = None, supersedes: str | None = None,
    *, review_number: int | None = None, job_instance_id: int | None = None,
) -> dict[str, Any]:
    decision = decision.upper(); categories = categories or []
    if decision not in HUMAN_DECISIONS: raise ValueError(f"invalid decision: {decision}")
    if expected_tier and expected_tier.upper() not in TIERS: raise ValueError(f"invalid expected tier: {expected_tier}")
    unknown = set(categories) - DISAGREEMENT_CATEGORIES
    if unknown: raise ValueError(f"invalid disagreement categories: {sorted(unknown)}")
    if ranking_agreement and (expected_tier or categories): raise ValueError("agreement cannot include expected tier or disagreement categories")
    selected = resolve_batch_job(
        batch, job_or_review_id, review_number=review_number,
        job_instance_id=job_instance_id,
    )
    records = load_judgments(judgments_path); current = current_judgments(records, batch["validation_batch_id"])
    existing = current.get((batch["validation_batch_id"], selected["job_instance_id"]))
    if existing and not supersedes: raise ValueError(f"current judgment exists; supersede {existing['judgment_id']}")
    if supersedes and (not existing or existing["judgment_id"] != supersedes): raise ValueError("supersedes must reference the current judgment for this batch/job")
    judgment = {
        "judgment_id": str(uuid.uuid4()), "validation_batch_id": batch["validation_batch_id"],
        "job_instance_id": selected["job_instance_id"], "job_observation_id": selected["job_observation_id"],
        "content_fingerprint": selected["content_fingerprint"], "opportunity_assessment_id": selected["opportunity_assessment_id"],
        "candidate_profile_id": batch["candidate"]["profile_id"], "candidate_profile_version": batch["candidate"]["version"],
        "semantic_assessor": batch["semantic"]["assessor_id"], "semantic_model": batch["semantic"]["model"],
        "semantic_contract_version": batch["semantic"]["contract_version"],
        "scoring_preference_fingerprint": batch["candidate"]["scoring_preference_fingerprint"],
        "reviewed_at": utc_now(), "decision": decision, "ranking_agreement": bool(ranking_agreement),
        "expected_tier": expected_tier.upper() if expected_tier else None, "note": note,
        "disagreement_categories": categories, "supersedes_judgment_id": supersedes,
    }
    path = Path(judgments_path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(judgment, ensure_ascii=False) + "\n"); handle.flush(); os.fsync(handle.fileno())
    return judgment


def calculate_metrics(batch: dict[str, Any], judgment_records: list[dict[str, Any]]) -> dict[str, Any]:
    current = current_judgments(judgment_records, batch["validation_batch_id"])
    reviewed = [(item, current[(batch["validation_batch_id"], item["job_instance_id"])]) for item in batch["selected_jobs"] if (batch["validation_batch_id"], item["job_instance_id"]) in current]
    top = [(item, judgment) for item, judgment in reviewed if item["stratum"] == "TOP_RANKED"]
    applies = [(item, judgment) for item, judgment in reviewed if judgment["decision"] == "APPLY"]
    below = [(item, judgment) for item, judgment in reviewed if item["stratum"] != "TOP_RANKED"]
    below_applies = [(item, judgment) for item, judgment in below if judgment["decision"] == "APPLY"]
    false_negatives = [(item, judgment) for item, judgment in below_applies if item["recommendation"] == "LOW_PRIORITY"]
    missed_attention = [(item, judgment) for item, judgment in below if judgment["decision"] in {"APPLY", "REVIEW"} and item["recommendation"] == "LOW_PRIORITY"]
    confusion: dict[str, Counter] = defaultdict(Counter)
    by_tier: dict[str, Counter] = defaultdict(Counter)
    disagreements: dict[str, Counter] = defaultdict(Counter)
    for item, judgment in reviewed:
        confusion[item["recommendation"]][judgment["decision"]] += 1
        by_tier[item["tier"]]["count"] += 1
        by_tier[item["tier"]]["APPLY"] += judgment["decision"] == "APPLY"
        by_tier[item["tier"]]["ATTENTION"] += judgment["decision"] in {"APPLY", "REVIEW"}
        for category in judgment.get("disagreement_categories", []):
            disagreements[category][judgment["decision"]] += 1
            disagreements[category][item["tier"]] += 1
    source = batch["preflight_snapshot"]
    usage = (batch.get("usage_run") or {}).get("summary")
    sample_size = len(batch["selected_jobs"]); reviewed_count = len(reviewed)
    strata_present = {item["stratum"] for item, _ in reviewed}
    sufficient = reviewed_count >= 20 and reviewed_count >= 0.8 * sample_size and strata_present >= {item["stratum"] for item in batch["selected_jobs"]}
    top_attention = sum(j["decision"] in {"APPLY", "REVIEW"} for _, j in top) / len(top) if top else None
    shortlist_recall = sum(item["recommendation"] not in {"LOW_PRIORITY", "INELIGIBLE"} for item, _ in applies) / len(applies) if applies else None
    tier_agreement = sum(j["ranking_agreement"] for _, j in reviewed) / reviewed_count if reviewed else None
    control_reviewed = [(i, j) for i, j in reviewed if i["stratum"] == "LOW_CONTROL"]
    low_control_agreement = sum(j["decision"] == "DONT_APPLY" for _, j in control_reviewed) / len(control_reviewed) if control_reviewed else None
    verdict = "NOT_READY"
    if sufficient and None not in (top_attention, shortlist_recall, tier_agreement, low_control_agreement):
        if shortlist_recall >= .9 and len(false_negatives) <= 1 and top_attention >= .7 and tier_agreement >= .6 and low_control_agreement >= .8 and (not usage or usage.get("failures", 0) / max(1, usage.get("jobs_processed", 0)) <= .05): verdict = "GO"
        elif shortlist_recall < .75 or top_attention < .5 or (below and len(false_negatives) / len(below) > .2): verdict = "NO_GO"
        else: verdict = "CONDITIONAL_GO"
    return {
        "sampling_warning": "Stratified reviewed sample; metrics are not unbiased market-wide estimates.",
        "reviewed": reviewed_count, "sample_size": sample_size, "sufficient_for_directional_verdict": sufficient,
        "top_stratum": {"reviewed": len(top), "strict_top_apply_rate": sum(j["decision"] == "APPLY" for _, j in top) / len(top) if top else None, "top_attention_acceptance": top_attention},
        "reviewed_sample": {"strict_apply_recall": sum(item["recommendation"] == "APPLY" for item, _ in applies) / len(applies) if applies else None, "shortlist_apply_recall": shortlist_recall, "ranking_agreement": tier_agreement, "recommendation_confusion_matrix": {key: dict(value) for key, value in confusion.items()}},
        "below_cutoff": {"reviewed": len(below), "human_apply_count": len(below_applies), "human_apply_false_negative_count": len(false_negatives), "human_apply_false_negative_rate": len(false_negatives) / len(below_applies) if below_applies else None, "missed_attention_count": len(missed_attention)},
        "by_tier": {tier: {"count": value["count"], "apply_rate": value["APPLY"] / value["count"], "attention_acceptance": value["ATTENTION"] / value["count"]} for tier, value in by_tier.items()},
        "semantic_operation": usage,
        "market_operation": {"active_jobs": source["active_jobs"], "detail_missing_jobs": source["unassessable_detail_missing_count"], **source["eligibility"], "candidate_market_status": source.get("market_status"), "jobs_eligible_for_semantic_processing": source.get("jobs_eligible_for_semantic_processing"), "latest_run_event_counts": source["latest_run_event_counts"], "source_failures_or_incomplete": source["source_failures_or_incomplete"]},
        "disagreements": {key: dict(value) for key, value in disagreements.items()},
        "verdict": verdict, "verdict_note": "Experimental directional gate, not a production SLA.",
    }


def render_validation_report(batch: dict[str, Any], metrics: dict[str, Any]) -> str:
    return "\n".join([
        f"# Live Validation Results — {batch['validation_batch_id']}", "",
        f"Reviewed: {metrics['reviewed']}/{metrics['sample_size']}",
        f"Directional verdict: **{metrics['verdict']}**", "",
        f"> {metrics['sampling_warning']}", "",
        "## Metrics", "", "```json", json.dumps(metrics, ensure_ascii=False, indent=2), "```", "",
    ])


def generate_report(batch: dict[str, Any], judgments_path: str | Path, output_root: str | Path) -> tuple[dict[str, Any], Path]:
    metrics = calculate_metrics(batch, load_judgments(judgments_path))
    path = Path(output_root) / batch["validation_batch_id"] / "validation_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_validation_report(batch, metrics), encoding="utf-8")
    return metrics, path


def _print_preflight(value: dict[str, Any]) -> None:
    display = {key: value[key] for key in (
        "configured_employers", "active_jobs", "active_jobs_with_usable_semantic_details",
        "unassessable_detail_missing_count", "market_status", "eligibility",
        "jobs_eligible_for_semantic_processing", "compatible_luna_cache_hits",
        "out_of_scope_existing_cache_hits",
        "luna_cache_misses", "expected_external_calls", "estimated_semantic_cost_usd",
        "source_failures_or_incomplete", "candidate", "semantic", "note",
    )}
    print(json.dumps(display, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Live Decision Validation experiment")
    parser.add_argument("--database", default="output/opportunity_radar.sqlite3")
    parser.add_argument("--companies", default="config/companies.yaml")
    parser.add_argument("--candidate", default="config/candidate.yaml")
    parser.add_argument("--taxonomy", default="config/taxonomy.yaml")
    parser.add_argument("--semantic-config", default="config/semantic_experiment.yaml")
    parser.add_argument("--market-rules", default="config/market_status_rules.yaml")
    parser.add_argument("--roi-results", default="output/semantic_roi_experiment.json")
    parser.add_argument("--output-root", default="output/live_validation")
    parser.add_argument("--judgments", default="data/live_validation/judgments.jsonl")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    assess = sub.add_parser("assess"); assess.add_argument("--run-id")
    prepare = sub.add_parser("prepare"); prepare.add_argument("--batch-id"); prepare.add_argument("--seed"); prepare.add_argument("--usage-run")
    record = sub.add_parser("record"); record.add_argument("batch_id"); record.add_argument("record_values", nargs="+", metavar="ID/DECISION"); identity = record.add_mutually_exclusive_group(); identity.add_argument("--review-number", type=int); identity.add_argument("--job-instance-id", type=int); agreement = record.add_mutually_exclusive_group(required=True); agreement.add_argument("--agree", action="store_true"); agreement.add_argument("--disagree", action="store_true"); record.add_argument("--expected-tier", choices=sorted(TIERS)); record.add_argument("--category", action="append", default=[], choices=sorted(DISAGREEMENT_CATEGORIES)); record.add_argument("--note"); record.add_argument("--supersedes")
    report = sub.add_parser("report"); report.add_argument("batch_id")
    args = parser.parse_args()
    common = (
        args.database, args.companies, args.candidate, args.taxonomy,
        args.semantic_config, args.roi_results, args.market_rules,
    )
    if args.command == "preflight":
        value = build_preflight(*common); _print_preflight(value); return 0
    if args.command == "assess":
        value = run_luna_assessment(args.database, args.output_root, args.companies, args.candidate, args.taxonomy, args.semantic_config, args.roi_results, args.run_id, args.market_rules); print(json.dumps({"validation_run_id": value["validation_run_id"], "summary": value["summary"], "manifest_path": value["manifest_path"]}, indent=2)); return 0 if not value["summary"]["failures"] else 1
    if args.command == "prepare":
        value = prepare_batch(args.database, args.output_root, args.candidate, args.taxonomy, args.semantic_config, args.companies, args.roi_results, args.batch_id, args.seed, args.usage_run, args.market_rules); print(json.dumps({"validation_batch_id": value["validation_batch_id"], "batch_path": value["batch_path"], "review_path": value["review_path"]}, indent=2)); return 0
    batch = load_batch(args.output_root, args.batch_id)
    if args.command == "record":
        explicit = args.review_number is not None or args.job_instance_id is not None
        expected_values = 1 if explicit else 2
        if len(args.record_values) != expected_values:
            parser.error(
                "record requires DECISION with an explicit identity, or positional ID DECISION"
            )
        job_or_review_id = None if explicit else args.record_values[0]
        decision = args.record_values[-1].upper()
        if decision not in HUMAN_DECISIONS:
            parser.error(f"invalid decision: {decision}")
        value = append_judgment(
            batch, args.judgments, job_or_review_id, decision, args.agree,
            args.expected_tier, args.note, args.category, args.supersedes,
            review_number=args.review_number, job_instance_id=args.job_instance_id,
        ); print(json.dumps(value, ensure_ascii=False, indent=2)); return 0
    metrics, path = generate_report(batch, args.judgments, args.output_root); print(json.dumps({"report": str(path), "verdict": metrics["verdict"], "reviewed": metrics["reviewed"]}, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
