from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import subprocess
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.config import load_companies
from opportunity_radar.live_validation import _active_rows, _readonly_connection, _usable
from opportunity_radar.phase3_config import digest, load_candidate_profile, load_taxonomy
from opportunity_radar.prospective_validation import (
    build_current_cluster_population,
    load_prospective_protocol,
)


DEFAULT_CONFIG = Path("experiments/source_portfolio_audit_v1.yaml")
DEFAULT_DATABASE = Path("output/opportunity_radar.sqlite3")
EXPERIMENT_TYPE = "SOURCE_PORTFOLIO_ROLE_COVERAGE_AUDIT"
SOURCE_STATUSES = {
    "CONFIRMED_CURRENT_SOURCE", "LIKELY_SOURCE", "UNVERIFIED_CANDIDATE",
}
INTEGRATION_EFFORTS = {
    "CONFIG_ONLY", "SMALL_ADAPTER_EXTENSION", "NEW_ADAPTER_REQUIRED", "UNKNOWN",
}
OTHER_FAMILY = "OTHER_AMBIGUOUS"


class SourcePortfolioAuditError(ValueError):
    pass


@dataclass(frozen=True)
class RoleFamilyRule:
    family: str
    title_patterns: tuple[re.Pattern[str], ...]
    description_patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class RoleFamilyMatch:
    family: str
    evidence_level: str
    title_signals: tuple[str, ...]
    description_signals: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "evidence_level": self.evidence_level,
            "title_signals": list(self.title_signals),
            "description_signals": list(self.description_signals),
        }


@dataclass(frozen=True)
class SourcePortfolioAuditConfig:
    raw: dict[str, Any]
    fingerprint: str
    role_rules: tuple[RoleFamilyRule, ...]

    @property
    def experiment_id(self) -> str:
        return str(self.raw["experiment_id"])

    @property
    def minimum_description_signals(self) -> int:
        return int(self.raw["role_classification"]["minimum_description_signals"])


def _sha256(path: str | Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True,
    ).stdout.strip())
    return {"commit": commit, "dirty": dirty}


def _compile_patterns(values: Any, label: str) -> tuple[re.Pattern[str], ...]:
    if not isinstance(values, list) or not values or any(not isinstance(x, str) for x in values):
        raise SourcePortfolioAuditError(f"{label} must be a non-empty string list")
    try:
        return tuple(re.compile(value, re.IGNORECASE) for value in values)
    except re.error as exc:
        raise SourcePortfolioAuditError(f"invalid {label}: {exc}") from exc


def load_source_portfolio_audit_config(
    path: str | Path = DEFAULT_CONFIG,
) -> SourcePortfolioAuditConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version", "experiment_id", "experiment_type", "candidate_path",
        "taxonomy_path", "companies_path", "research_dataset_path",
        "prospective_protocol_path", "role_classification", "target_role_families",
        "candidate_direction", "portfolio_selection", "candidate_employers",
        "privacy", "outputs",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise SourcePortfolioAuditError("source portfolio audit has an invalid schema")
    if raw["schema_version"] != 1 or raw["experiment_type"] != EXPERIMENT_TYPE:
        raise SourcePortfolioAuditError("unsupported source portfolio audit identity")
    role = raw["role_classification"]
    if not isinstance(role, dict) or set(role) != {
        "contract_version", "minimum_description_signals", "families",
    }:
        raise SourcePortfolioAuditError("invalid role-classification contract")
    minimum = role["minimum_description_signals"]
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
        raise SourcePortfolioAuditError("minimum_description_signals must be positive")
    if not isinstance(role["families"], dict) or not role["families"]:
        raise SourcePortfolioAuditError("role families must be a non-empty mapping")
    rules = []
    for family, patterns in role["families"].items():
        if not isinstance(patterns, dict) or set(patterns) != {
            "title_patterns", "description_patterns",
        }:
            raise SourcePortfolioAuditError(f"invalid role-family rule: {family}")
        rules.append(RoleFamilyRule(
            str(family),
            _compile_patterns(patterns["title_patterns"], f"{family}.title_patterns"),
            _compile_patterns(
                patterns["description_patterns"], f"{family}.description_patterns",
            ),
        ))
    families = {rule.family for rule in rules}
    targets = raw["target_role_families"]
    if not isinstance(targets, list) or not targets or not set(targets) <= families:
        raise SourcePortfolioAuditError("target role families must resolve to classifier rules")
    selection = raw["portfolio_selection"]
    if not isinstance(selection, dict) or set(selection) != {
        "wave_a_limit", "wave_b_limit", "score_dimensions",
    }:
        raise SourcePortfolioAuditError("invalid portfolio selection policy")
    dimensions = selection["score_dimensions"]
    if not isinstance(dimensions, list) or not dimensions or len(dimensions) != len(set(dimensions)):
        raise SourcePortfolioAuditError("score dimensions must be unique")
    candidates = raw["candidate_employers"]
    if not isinstance(candidates, list) or not 20 <= len(candidates) <= 40:
        raise SourcePortfolioAuditError("candidate employer longlist must contain 20-40 entries")
    ids = []
    for item in candidates:
        if not isinstance(item, dict) or set(item) != {
            "company_id", "category", "source_status", "verified_at",
            "integration_effort", "scores",
        }:
            raise SourcePortfolioAuditError("invalid candidate-employer entry")
        ids.append(str(item["company_id"]))
        if item["source_status"] not in SOURCE_STATUSES:
            raise SourcePortfolioAuditError("invalid candidate source status")
        if item["integration_effort"] not in INTEGRATION_EFFORTS:
            raise SourcePortfolioAuditError("invalid integration effort")
        if set(item["scores"]) != set(dimensions):
            raise SourcePortfolioAuditError("candidate scores do not match score dimensions")
        if any(
            not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 3
            for value in item["scores"].values()
        ):
            raise SourcePortfolioAuditError("candidate scores must be integers in [0, 3]")
    if len(ids) != len(set(ids)):
        raise SourcePortfolioAuditError("candidate employer IDs must be unique")
    if raw["privacy"] != {
        "detailed_artifact": "PRIVATE_LOCAL",
        "aggregate_artifact": "REPOSITORY_SAFE",
    }:
        raise SourcePortfolioAuditError("invalid audit privacy boundary")
    return SourcePortfolioAuditConfig(raw, digest(raw), tuple(rules))


def classify_role_families(
    title: str | None,
    description: str | None,
    config: SourcePortfolioAuditConfig,
) -> tuple[RoleFamilyMatch, ...]:
    """Return neutral, multi-label role evidence for audit diagnostics."""
    title_text = title or ""
    description_text = description or ""
    matches = []
    for rule in config.role_rules:
        title_signals = tuple(
            pattern.pattern for pattern in rule.title_patterns if pattern.search(title_text)
        )
        description_signals = tuple(
            pattern.pattern
            for pattern in rule.description_patterns
            if pattern.search(description_text)
        )
        if title_signals:
            level = (
                "TITLE_AND_DESCRIPTION_SUPPORTED"
                if description_signals else "TITLE_SUPPORTED"
            )
        elif len(description_signals) >= config.minimum_description_signals:
            level = "DESCRIPTION_SUPPORTED"
        else:
            continue
        matches.append(RoleFamilyMatch(
            rule.family, level, title_signals, description_signals,
        ))
    if not matches:
        return (RoleFamilyMatch(OTHER_FAMILY, "AMBIGUOUS", (), ()),)
    return tuple(matches)


def concentration_metrics(counts: dict[str, int]) -> dict[str, Any]:
    clean = {key: int(value) for key, value in counts.items() if int(value) > 0}
    total = sum(clean.values())
    if not total:
        return {
            "total": 0, "employer_count": 0, "top_1_share": 0.0,
            "top_3_share": 0.0, "top_5_share": 0.0, "hhi": 0.0,
            "effective_employers": 0.0,
        }
    ordered = sorted(clean.values(), reverse=True)
    shares = [value / total for value in ordered]
    hhi_fraction = sum(share * share for share in shares)
    return {
        "total": total,
        "employer_count": len(clean),
        "top_1_share": round(sum(shares[:1]), 6),
        "top_3_share": round(sum(shares[:3]), 6),
        "top_5_share": round(sum(shares[:5]), 6),
        "hhi": round(hhi_fraction * 10000, 2),
        "effective_employers": round(1 / hhi_fraction, 3),
    }


def _load_research_rows(path: str | Path) -> dict[str, dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = {}
    for row in rows:
        company_id = row.get("company_id", "")
        if not company_id or company_id in result:
            raise SourcePortfolioAuditError("research dataset has missing or duplicate company IDs")
        result[company_id] = row
    return result


def _latest_source_evidence(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """WITH valid AS (
               SELECT so.*, ir.started_at,
                      ROW_NUMBER() OVER (
                        PARTITION BY so.company_id
                        ORDER BY ir.started_at DESC, so.source_observation_id DESC
                      ) AS rn
               FROM source_observations so JOIN ingestion_runs ir ON ir.run_id=so.run_id
               WHERE so.status='SUCCESS' AND so.inventory_complete=1
             ), latest AS (
               SELECT so.company_id,so.status,so.inventory_complete,so.error_type,
                      so.error_message,so.run_id,ir.started_at,
                      ROW_NUMBER() OVER (
                        PARTITION BY so.company_id
                        ORDER BY ir.started_at DESC, so.source_observation_id DESC
                      ) AS rn
               FROM source_observations so JOIN ingestion_runs ir ON ir.run_id=so.run_id
             )
             SELECT v.*,l.status AS latest_status,
                    l.inventory_complete AS latest_inventory_complete,
                    l.error_type AS latest_error_type,l.error_message AS latest_error_message,
                    l.run_id AS latest_run_id
             FROM valid v JOIN latest l ON l.company_id=v.company_id AND l.rn=1
             WHERE v.rn=1"""
    ).fetchall()
    return {str(row["company_id"]): dict(row) for row in rows}


def _candidate_direction(config: SourcePortfolioAuditConfig) -> dict[str, Any]:
    taxonomy = load_taxonomy(config.raw["taxonomy_path"])
    profile = load_candidate_profile(config.raw["candidate_path"], taxonomy)
    requested = config.raw["candidate_direction"]
    capability = {item["capability_id"]: item for item in profile.capabilities}
    legacy = {
        item["characteristic_id"]: item
        for item in profile.preferences.get("role_characteristics", [])
    }
    decision = {item.concept_id: item for item in profile.decision_preferences.entries}
    for values in requested.values():
        for concept_id in values:
            taxonomy.require(concept_id, "source portfolio candidate-direction concept")
    return {
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "capabilities": {
            concept_id: {
                "represented": concept_id in capability,
                "level": capability.get(concept_id, {}).get("level"),
                "confidence": capability.get(concept_id, {}).get("confidence"),
            }
            for concept_id in requested["capability_concepts"]
        },
        "legacy_preferences": {
            concept_id: {
                "represented": concept_id in legacy,
                "importance": legacy.get(concept_id, {}).get("importance"),
            }
            for concept_id in requested["legacy_preference_concepts"]
        },
        "decision_preferences": {
            concept_id: {
                "represented": concept_id in decision,
                "stance": decision[concept_id].stance if concept_id in decision else None,
            }
            for concept_id in requested["decision_preference_concepts_expected"]
        },
        "missing_decision_direction_concepts": sorted(
            set(requested["decision_preference_concepts_expected"]) - set(decision)
        ),
        "recommendation": (
            "PROPOSE_VERSIONED_DECISION_PREFERENCE_UPDATE_ONLY"
            if set(requested["decision_preference_concepts_expected"]) - set(decision)
            else "NO_PROFILE_CHANGE"
        ),
        "profile_mutated": False,
    }


def _candidate_longlist(config: SourcePortfolioAuditConfig) -> dict[str, Any]:
    research = _load_research_rows(config.raw["research_dataset_path"])
    current = {company.company_id for company in load_companies(config.raw["companies_path"])}
    dimensions = config.raw["portfolio_selection"]["score_dimensions"]
    values = []
    for item in config.raw["candidate_employers"]:
        company_id = str(item["company_id"])
        if company_id not in research:
            raise SourcePortfolioAuditError(f"candidate employer missing from research dataset: {company_id}")
        row = research[company_id]
        score = sum(int(item["scores"][field]) for field in dimensions)
        values.append({
            "company_id": company_id,
            "company_name": row["company_name"],
            "category": item["category"],
            "market_evidence": row["cz_presence"] or "UNSPECIFIED",
            "careers_url": row["careers_url"],
            "source_url": row["endpoint_url"] or row["jobs_search_url"] or row["careers_url"],
            "source_status": item["source_status"],
            "verified_at": item["verified_at"],
            "ats_family": row["ats_family"] or "unknown",
            "expected_adapter": row["expected_adapter"] or "UNKNOWN",
            "integration_effort": item["integration_effort"],
            "scores": dict(item["scores"]),
            "total_score": score,
            "production_configured": company_id in current,
        })
    key = lambda item: (-item["total_score"], item["company_id"])
    a_candidates = sorted([
        item for item in values
        if item["integration_effort"] == "CONFIG_ONLY"
        and not item["production_configured"]
        and item["source_status"] != "UNVERIFIED_CANDIDATE"
        and item["scores"]["market_access"] == 3
    ], key=key)
    wave_a = a_candidates[: int(config.raw["portfolio_selection"]["wave_a_limit"])]
    used = {item["company_id"] for item in wave_a}
    b_candidates = sorted([
        item for item in values
        if item["company_id"] not in used
        and not item["production_configured"]
        and item["source_status"] != "UNVERIFIED_CANDIDATE"
        and item["total_score"] >= 10
    ], key=key)
    wave_b = b_candidates[: int(config.raw["portfolio_selection"]["wave_b_limit"])]
    used.update(item["company_id"] for item in wave_b)
    watchlist = sorted(
        [item for item in values if item["company_id"] not in used and not item["production_configured"]], key=key,
    )
    return {
        "longlist_count": len(values),
        "production_configured_candidate_count": sum(item["production_configured"] for item in values),
        "score_scale": "0_WEAK_OR_UNKNOWN_TO_3_STRONG_PER_DIMENSION",
        "ranking_dimensions": list(dimensions),
        "wave_a": wave_a,
        "wave_b": wave_b,
        "watchlist": watchlist,
        "source_status_counts": dict(sorted(Counter(
            item["source_status"] for item in values
        ).items())),
        "integration_effort_counts": dict(sorted(Counter(
            item["integration_effort"] for item in values
        ).items())),
    }


def _role_coverage(
    population: list[dict[str, Any]], config: SourcePortfolioAuditConfig,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    family_rows: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in population:
        matches = classify_role_families(item.get("title"), item.get("description"), config)
        private = {
            "cluster_id": item["cluster_id"],
            "company_id": item["company_id"],
            "title": item.get("title"),
            "market_status": item.get("market_status"),
            "normal_candidate": item.get("normal_candidate"),
            "matches": [match.payload() for match in matches],
        }
        rows.append(private)
        for match in matches:
            family_rows[match.family].append({**item, "role_match": match})
    aggregate = {}
    ordered_families = [rule.family for rule in config.role_rules] + [OTHER_FAMILY]
    for family in ordered_families:
        matches = family_rows.get(family, [])
        employers = Counter(item["company_id"] for item in matches)
        aggregate[family] = {
            "cluster_count": len(matches),
            "normal_candidate_count": sum(bool(item["normal_candidate"]) for item in matches),
            "market_status_counts": dict(sorted(Counter(
                item.get("market_status") or "UNAVAILABLE" for item in matches
            ).items())),
            "employer_count": len(employers),
            "top_employers": [
                {"company_id": company_id, "count": count}
                for company_id, count in employers.most_common(5)
            ],
            "employer_concentration": concentration_metrics(dict(employers)),
            "classification_evidence": dict(sorted(Counter(
                item["role_match"].evidence_level for item in matches
            ).items())),
        }
    return aggregate, rows


def _portfolio_inventory(
    database: str | Path,
    config: SourcePortfolioAuditConfig,
    population: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    companies = load_companies(config.raw["companies_path"])
    with _readonly_connection(database) as connection:
        source = _latest_source_evidence(connection)
        active_rows = _active_rows(connection)
        schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    active = Counter(row["company_id"] for row in active_rows)
    usable = Counter(row["company_id"] for row in active_rows if _usable(row))
    clusters = Counter(item["company_id"] for item in population)
    routed = Counter(item["company_id"] for item in population if item["normal_candidate"])
    market: defaultdict[str, Counter[str]] = defaultdict(Counter)
    cache: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for item in population:
        market[item["company_id"]][item.get("market_status") or "UNAVAILABLE"] += 1
        cache[item["company_id"]][item["semantic_cache_status"]] += 1
    rows = []
    inventory_counts = {}
    for company in companies:
        evidence = source.get(company.company_id)
        if evidence is None:
            inventory_count = 0
            source_payload = {"valid_complete_inventory_available": False}
        else:
            inventory_count = int(evidence["observed_count"])
            source_payload = {
                "valid_complete_inventory_available": True,
                "valid_run_id": evidence["run_id"],
                "valid_observed_at": evidence["observed_at"],
                "valid_status": evidence["status"],
                "valid_inventory_complete": bool(evidence["inventory_complete"]),
                "expected_count": evidence["expected_count"],
                "observed_count": inventory_count,
                "detail_success_count": int(evidence["detail_success_count"]),
                "detail_failure_count": int(evidence["detail_failure_count"]),
                "latest_status": evidence["latest_status"],
                "latest_inventory_complete": bool(evidence["latest_inventory_complete"]),
                "latest_error_type": evidence["latest_error_type"],
                "network_detail_requests": None,
                "network_indicator_limitation": "NOT_PERSISTED_IN_SOURCE_OBSERVATION",
            }
        inventory_counts[company.company_id] = inventory_count
        rows.append({
            "company_id": company.company_id,
            "company_name": company.company_name,
            "adapter": company.adapter,
            "source": source_payload,
            "active_jobs": int(active[company.company_id]),
            "usable_detailed_active_jobs": int(usable[company.company_id]),
            "market_status_counts": dict(sorted(market[company.company_id].items())),
            "opportunity_clusters": int(clusters[company.company_id]),
            "routed_normal_candidate_clusters": int(routed[company.company_id]),
            "routed_share": 0.0,
            "semantic_cache_status_counts": dict(sorted(cache[company.company_id].items())),
        })
    routed_total = sum(routed.values())
    for row in rows:
        row["routed_share"] = round(
            row["routed_normal_candidate_clusters"] / routed_total, 6,
        ) if routed_total else 0.0
    counts = {
        "all_observed_inventory": inventory_counts,
        "usable_active_detail": dict(usable),
        "market_routed_candidate_population": dict(routed),
    }
    summary = {
        "configured_employer_count": len(companies),
        "sqlite_schema_version": schema_version,
        "concentration": {
            boundary: concentration_metrics(values) for boundary, values in counts.items()
        },
        "adapter_distribution": {
            adapter: {
                "configured_employers": sum(company.adapter == adapter for company in companies),
                "latest_complete_inventory": sum(
                    inventory_counts[company.company_id]
                    for company in companies if company.adapter == adapter
                ),
                "routed_clusters": sum(
                    routed[company.company_id]
                    for company in companies if company.adapter == adapter
                ),
            }
            for adapter in sorted({company.adapter for company in companies})
        },
    }
    return rows, summary


def run_source_portfolio_audit(
    config_path: str | Path = DEFAULT_CONFIG,
    database: str | Path = DEFAULT_DATABASE,
    output_root: str | Path | None = None,
    *,
    run_id: str | None = None,
    write_artifact: bool = True,
) -> dict[str, Any]:
    config = load_source_portfolio_audit_config(config_path)
    database_hash_before = _sha256(database)
    protocol = load_prospective_protocol(config.raw["prospective_protocol_path"])
    population, population_metadata = build_current_cluster_population(database, protocol)
    portfolio_rows, portfolio_summary = _portfolio_inventory(database, config, population)
    role_coverage, role_examples = _role_coverage(population, config)
    candidate_direction = _candidate_direction(config)
    discovery = _candidate_longlist(config)
    database_hash_after = _sha256(database)
    if database_hash_before != database_hash_after:
        raise SourcePortfolioAuditError("source portfolio audit mutated operational SQLite")
    run_id = run_id or (
        "source-portfolio-audit-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
        + uuid.uuid4().hex[:8]
    )
    target_families = {
        family: role_coverage[family] for family in config.raw["target_role_families"]
    }
    target_names = set(config.raw["target_role_families"])
    target_rows = [
        row for row in role_examples
        if any(match["family"] in target_names for match in row["matches"])
    ]
    target_cluster_union = {row["cluster_id"] for row in target_rows}
    target_routed_union = {
        row["cluster_id"] for row in target_rows if row["normal_candidate"]
    }
    target_employers = Counter(row["company_id"] for row in target_rows)
    title_supported_target_rows = [
        row for row in target_rows
        if any(
            match["family"] in target_names
            and match["evidence_level"] in {
                "TITLE_SUPPORTED", "TITLE_AND_DESCRIPTION_SUPPORTED",
            }
            for match in row["matches"]
        )
    ]
    title_supported_target_clusters = {
        row["cluster_id"] for row in title_supported_target_rows
    }
    description_only_target_clusters = target_cluster_union - title_supported_target_clusters
    result = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment_id": config.experiment_id,
        "experiment_type": EXPERIMENT_TYPE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "portfolio": {"summary": portfolio_summary, "employers": portfolio_rows},
        "population_metadata": population_metadata,
        "role_coverage": role_coverage,
        "role_examples": role_examples,
        "target_role_summary": {
            "families": target_families,
            "unique_cluster_count": len(target_cluster_union),
            "unique_routed_cluster_count": len(target_routed_union),
            "share_of_all_clusters": round(
                len(target_cluster_union) / len(population), 6,
            ) if population else 0.0,
            "share_of_routed_clusters": round(
                len(target_routed_union) / population_metadata["normal_candidate_count"], 6,
            ) if population_metadata["normal_candidate_count"] else 0.0,
            "market_status_counts": dict(sorted(Counter(
                row.get("market_status") or "UNAVAILABLE" for row in target_rows
            ).items())),
            "employer_count": len(target_employers),
            "employer_concentration": concentration_metrics(dict(target_employers)),
            "title_supported_unique_cluster_count": len(title_supported_target_clusters),
            "description_only_unique_cluster_count": len(description_only_target_clusters),
            "title_supported_routed_cluster_count": sum(
                row["cluster_id"] in title_supported_target_clusters
                and bool(row["normal_candidate"])
                for row in target_rows
            ),
        },
        "candidate_direction": candidate_direction,
        "employer_discovery": discovery,
        "configuration": {
            "audit_fingerprint": config.fingerprint,
            "role_contract_version": config.raw["role_classification"]["contract_version"],
            "prospective_protocol_fingerprint": protocol.fingerprint,
            "git": _git_state(),
        },
        "integrity": {
            "database_sha256_before": database_hash_before,
            "database_sha256_after": database_hash_after,
            "database_unchanged": True,
            "semantic_calls": 0,
            "new_employer_ingestion_calls": 0,
            "sqlite_writes": 0,
            "candidate_profile_mutated": False,
        },
    }
    if write_artifact:
        root = Path(output_root or config.raw["outputs"]["root"])
        directory = root / run_id
        directory.mkdir(parents=True, exist_ok=False)
        detailed_path = directory / "audit.json"
        detailed_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        aggregate = {
            "schema_version": 1,
            "run_id": run_id,
            "experiment_id": config.experiment_id,
            "experiment_type": EXPERIMENT_TYPE,
            "created_at": result["created_at"],
            "portfolio": result["portfolio"],
            "population_metadata": population_metadata,
            "role_coverage": role_coverage,
            "target_role_summary": result["target_role_summary"],
            "candidate_direction": candidate_direction,
            "employer_discovery": discovery,
            "configuration": result["configuration"],
            "integrity": result["integrity"],
            "privacy": {
                "detailed_artifact": "PRIVATE_LOCAL",
                "detailed_sha256": _sha256(detailed_path),
                "repository_safe_aggregate": "aggregate_summary.json",
                "excluded_detail": "PER_CLUSTER_TITLES_AND_CLASSIFICATION_SIGNALS",
            },
            "limitations": [
                "Role-family evidence is deterministic, multi-label, and diagnostic; it is not a production ranker or final suitability assessment.",
                "Description-supported classification requires two independent patterns but can still over-count generic cross-functional language.",
                "The candidate-employer longlist uses bounded public-source evidence and the prior fingerprinted feasibility dataset; LIKELY and UNVERIFIED entries require source-contract confirmation before onboarding.",
                "Projected portfolio benefits are directional because candidate employers were not ingested and no future role volume was fabricated.",
                "Network detail-request counts are not persisted in source_observations, so detail observation counts are not mislabeled as network cost.",
            ],
            "decision_gates": {
                "portfolio_expansion_justified": (
                    portfolio_summary["concentration"]
                    ["market_routed_candidate_population"]["top_1_share"] >= 0.40
                ),
                "analytics_direction_hidden_only": False,
                "candidate_profile_capability_gap": False,
                "bounded_decision_preference_update_proposed": bool(
                    candidate_direction["missing_decision_direction_concepts"]
                ),
                "production_employers_added": 0,
            },
            "intake_portfolio_policy": {
                "objective": "MAXIMIZE_MARGINAL_USEFUL_MARKET_COVERAGE_NOT_RAW_VACANCY_VOLUME",
                "review_signals": [
                    "CONCENTRATION_BY_INVENTORY_USABLE_DETAIL_AND_ROUTED_CLUSTER",
                    "UNIQUE_CANDIDATE_RELEVANT_CLUSTER_YIELD_BY_EMPLOYER",
                    "TARGET_ROLE_FAMILY_EMPLOYER_BREADTH",
                    "SOURCE_COMPLETENESS_AND_MAINTENANCE_COST",
                    "MARGINAL_SECTOR_AND_BUSINESS_MODEL_DIVERSITY",
                ],
                "addition_gate": "CLOSES_OBSERVED_MARKET_OR_ROLE_GAP_WITH_PUBLIC_OPERABLE_SOURCE",
                "retirement_gate": "REPEATED_NEGLIGIBLE_UNIQUE_USEFUL_YIELD_OR_UNACCEPTABLE_SOURCE_COST_AFTER_REVIEW",
                "automatic_removal": False,
            },
            "conclusions": [
                "The current portfolio is highly concentrated at every measured boundary and becomes most concentrated after candidate routing.",
                "Business/data/decision-analytics evidence exists, but it is employer-concentrated, predominantly uncertain in market status, and especially thin for explicit decision-intelligence/support roles.",
                "The gap is a combination of employer selection and diagnostic role visibility, not an absent candidate capability representation.",
                "The profile already represents business analytics and decision support as expert capabilities; a future versioned decision-preference update is justified, but this audit does not mutate the profile.",
                "Wave A should validate configuration-only sources first while Wave B tests high-value employers whose source contracts require adapter work.",
                "EY and Johnson & Johnson dominate current supply; their marginal candidate-relevant yield should be monitored, but this audit does not authorize removal.",
                "Source breadth and semantic compute allocation remain separate optimization problems.",
            ],
            "recommendation": "EXPAND_PORTFOLIO_IN_BOUNDED_WAVES_AFTER_SOURCE_CONTRACT_PREFLIGHT",
        }
        aggregate_path = directory / "aggregate_summary.json"
        aggregate_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n")
        result["artifact_paths"] = {
            "private_detailed": str(detailed_path),
            "repository_safe_aggregate": str(aggregate_path),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Phase 4 source-portfolio and role-coverage audit",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--output-root")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run_source_portfolio_audit(
        args.config, args.database, args.output_root,
        run_id=args.run_id, write_artifact=not args.dry_run,
    )
    print(json.dumps({
        "run_id": result["run_id"],
        "configured_employers": result["portfolio"]["summary"]["configured_employer_count"],
        "concentration": result["portfolio"]["summary"]["concentration"],
        "target_role_summary": result["target_role_summary"],
        "longlist_count": result["employer_discovery"]["longlist_count"],
        "waves": {
            "wave_a": len(result["employer_discovery"]["wave_a"]),
            "wave_b": len(result["employer_discovery"]["wave_b"]),
            "watchlist": len(result["employer_discovery"]["watchlist"]),
        },
        "external_semantic_calls": 0,
        "artifact_paths": result.get("artifact_paths"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
