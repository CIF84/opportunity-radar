from __future__ import annotations

from typing import Any


def coverage_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Deterministic SPEC-015 before/after arithmetic over source-portfolio receipts."""
    b = before["portfolio"]["summary"]
    a = after["portfolio"]["summary"]
    bp = before["population_metadata"]
    ap = after["population_metadata"]
    bt = before["target_role_summary"]
    at = after["target_role_summary"]
    boundaries = {}
    for key in ("all_observed_inventory", "usable_active_detail", "market_routed_candidate_population"):
        boundaries[key] = {
            metric: {"before": b["concentration"][key][metric], "after": a["concentration"][key][metric], "delta": round(a["concentration"][key][metric] - b["concentration"][key][metric], 6)}
            for metric in ("total", "employer_count", "top_1_share", "top_3_share", "top_5_share", "hhi", "effective_employers")
        }
    return {
        "configured_employers": {"before": b["configured_employer_count"], "after": a["configured_employer_count"], "delta": a["configured_employer_count"] - b["configured_employer_count"]},
        "boundaries": boundaries,
        "opportunity_coverage": {
            key: {"before": bp.get(key, 0), "after": ap.get(key, 0), "delta": ap.get(key, 0) - bp.get(key, 0)}
            for key in ("active_job_count", "active_usable_detail_count", "cluster_count", "normal_candidate_count")
        },
        "target_role_summary": {
            key: {"before": bt[key], "after": at[key], "delta": at[key] - bt[key]}
            for key in ("unique_cluster_count", "unique_routed_cluster_count", "title_supported_unique_cluster_count", "description_only_unique_cluster_count")
        },
    }
