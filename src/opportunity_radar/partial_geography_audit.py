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

from opportunity_radar.eligibility import evaluate_eligibility
from opportunity_radar.live_validation import (
    _active_rows,
    _semantic_job,
    _usable,
    observed_luna_cost,
)
from opportunity_radar.market_status import (
    EVALUATOR_VERSION,
    CurrentCandidateMarketAssessment,
    CurrentCandidateMarketStatus,
    MarketReasonCode,
    evaluate_current_candidate_market,
    load_market_normalization_rules,
)
from opportunity_radar.phase3_config import digest, load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import SemanticJobInput
from opportunity_radar.source_portfolio_audit import (
    classify_role_families,
    load_source_portfolio_audit_config,
)


DEFAULT_CONFIG = Path("experiments/partial_geography_semantics_v1.yaml")
EXPERIMENT_TYPE = "PARTIAL_GEOGRAPHY_SEMANTICS_AUDIT"


class PartialGeographyAuditError(ValueError):
    pass


@dataclass(frozen=True)
class PartialGeographyAuditConfig:
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


def load_partial_geography_audit_config(
    path: str | Path = DEFAULT_CONFIG,
) -> PartialGeographyAuditConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required = {
        "schema_version", "experiment_id", "experiment_type", "specification",
        "database_path", "candidate_path", "taxonomy_path", "market_rules_path",
        "role_audit_config_path", "truth_table_fixture_path",
        "historical_regression_fixture_path", "semantic_roi_results_path",
        "mews_company_id", "frozen_identity", "privacy", "outputs",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise PartialGeographyAuditError("partial-geography audit has an invalid schema")
    if raw["schema_version"] != 1 or raw["experiment_type"] != EXPERIMENT_TYPE:
        raise PartialGeographyAuditError("unsupported partial-geography audit identity")
    frozen = raw["frozen_identity"]
    if not isinstance(frozen, dict) or set(frozen) != {
        "previous_evaluator_version", "promoted_evaluator_version",
        "market_access_policy_fingerprint", "semantic_profile_fingerprint",
    }:
        raise PartialGeographyAuditError("invalid frozen identity")
    if frozen["previous_evaluator_version"] != "phase4-current-candidate-market-v2":
        raise PartialGeographyAuditError("unexpected previous evaluator identity")
    if frozen["promoted_evaluator_version"] != EVALUATOR_VERSION:
        raise PartialGeographyAuditError("promoted evaluator identity does not match runtime")
    if raw["privacy"] != {
        "detailed_artifact": "PRIVATE_LOCAL",
        "aggregate_artifact": "REPOSITORY_SAFE",
    }:
        raise PartialGeographyAuditError("invalid partial-geography privacy boundary")
    for key in (
        "specification", "database_path", "candidate_path", "taxonomy_path",
        "market_rules_path", "role_audit_config_path", "truth_table_fixture_path",
        "historical_regression_fixture_path", "semantic_roi_results_path",
    ):
        if not Path(raw[key]).exists():
            raise PartialGeographyAuditError(f"configured path does not exist: {raw[key]}")
    return PartialGeographyAuditConfig(raw, digest(raw))


def _fixture_job(item: dict[str, Any]) -> SemanticJobInput:
    location = item["job"]
    locations = () if not location["location"] else ({
        "raw": location["location"],
        "city": location.get("city"),
        "region": None,
        "country": location.get("country"),
    },)
    return SemanticJobInput(
        "Truth Table Fixture", "Fixture role", location.get("description", ""),
        locations, location["work_mode"],
    )


def _historical_job(item: dict[str, Any]) -> SemanticJobInput:
    job = item["job"]
    return SemanticJobInput(
        job["company_name"], job.get("title"), job.get("description", ""),
        tuple(job.get("locations", [])), job.get("work_mode", "unspecified"),
        job.get("employment_type"), job.get("department"),
    )


def _fixture_results(
    path: str | Path,
    candidate: Any,
    rules: Any,
    builder: Any,
) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("fixture_version") != 1 or not isinstance(raw.get("cases"), list):
        raise PartialGeographyAuditError(f"invalid fixture: {path}")
    results = []
    for item in raw["cases"]:
        assessment = evaluate_current_candidate_market(builder(item), candidate, rules)
        results.append({
            "case_id": item["case_id"],
            "expected": item["expected"],
            "actual": assessment.status.value,
            "passed": item["expected"] == assessment.status.value,
            "reason_codes": [reason.code.value for reason in assessment.reasons],
        })
    return results


def _legacy_status(assessment: CurrentCandidateMarketAssessment) -> str:
    """Reconstruct v2 only at the one branch changed by SPEC-017."""
    codes = {reason.code for reason in assessment.reasons}
    if (
        assessment.status is CurrentCandidateMarketStatus.UNCERTAIN
        and MarketReasonCode.ACCEPTED_COUNTRY_CITY_UNKNOWN in codes
    ):
        return CurrentCandidateMarketStatus.OUT_OF_SCOPE.value
    return assessment.status.value


def _effective_mode(assessment: CurrentCandidateMarketAssessment) -> str:
    return next(
        (
            evidence.normalized_value
            for evidence in assessment.evidence
            if evidence.kind == "work_mode" and evidence.normalized_value
        ),
        "unspecified",
    )


def _semantic_assessment_count(connection: sqlite3.Connection) -> int:
    try:
        return int(connection.execute("SELECT COUNT(*) FROM semantic_assessments").fetchone()[0])
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return 0
        raise


def _mews_cache_count(connection: sqlite3.Connection, profile: Any) -> int:
    try:
        return int(connection.execute(
            """SELECT COUNT(DISTINCT ji.job_instance_id)
               FROM job_instances ji
               JOIN job_observations jo ON jo.job_observation_id=ji.latest_observation_id
               JOIN semantic_assessments sa
                 ON sa.job_instance_id=ji.job_instance_id
                AND sa.content_fingerprint=jo.fingerprint
                AND sa.semantic_profile_fingerprint=?
               WHERE ji.lifecycle_state='ACTIVE' AND ji.company_id='mews'""",
            (profile.semantic_profile_fingerprint,),
        ).fetchone()[0])
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return 0
        raise


def _corpus_replay(
    database: str | Path,
    candidate: Any,
    rules: Any,
    role_config: Any,
    mews_company_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    uri = f"file:{Path(database).resolve()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    try:
        rows = [row for row in _active_rows(connection) if _usable(row)]
        semantic_rows = _semantic_assessment_count(connection)
        mews_cache_hits = _mews_cache_count(connection, candidate)
    finally:
        connection.close()

    before: Counter[str] = Counter()
    after: Counter[str] = Counter()
    transitions: Counter[str] = Counter()
    changed_employers: Counter[str] = Counter()
    changed_modes: Counter[str] = Counter()
    changed_reasons: Counter[str] = Counter()
    changed_completeness: Counter[str] = Counter()
    target_families = set(role_config.raw["target_role_families"])
    changed_target_families: Counter[str] = Counter()
    mews_target_families: Counter[str] = Counter()
    detailed = []
    mews_rows = []

    for row in rows:
        job = _semantic_job(row["snapshot"])
        assessment = evaluate_current_candidate_market(job, candidate, rules)
        old_status = _legacy_status(assessment)
        new_status = assessment.status.value
        before[old_status] += 1
        after[new_status] += 1
        transitions[f"{old_status} -> {new_status}"] += 1
        reason_codes = [reason.code.value for reason in assessment.reasons]
        mode = _effective_mode(assessment)
        if old_status != new_status:
            changed_employers[row["company_id"]] += 1
            changed_modes[mode] += 1
            changed_reasons.update(reason_codes)
            changed_completeness["ACCEPTED_COUNTRY_CITY_ABSENT"] += 1
            matches = classify_role_families(
                row["snapshot"].get("title"), row["snapshot"].get("description"),
                role_config,
            )
            for match in matches:
                if match.family in target_families:
                    changed_target_families[match.family] += 1
            detailed.append({
                "job_instance_id": row["job_instance_id"],
                "company_id": row["company_id"],
                "title": row["snapshot"].get("title"),
                "locations": row["snapshot"].get("locations", []),
                "stored_work_mode": row["snapshot"].get("work_mode", "unspecified"),
                "effective_work_mode": mode,
                "before": old_status,
                "after": new_status,
                "reason_codes": reason_codes,
            })
        if row["company_id"] == mews_company_id:
            eligibility = evaluate_eligibility(job, candidate).status.value
            matches = classify_role_families(
                row["snapshot"].get("title"), row["snapshot"].get("description"),
                role_config,
            )
            target_matches = sorted({
                match.family for match in matches if match.family in target_families
            })
            mews_target_families.update(target_matches)
            mews_rows.append({
                "job_instance_id": row["job_instance_id"],
                "stored_work_mode": row["snapshot"].get("work_mode", "unspecified"),
                "effective_work_mode": mode,
                "city_absent": all(not location.get("city") for location in job.locations),
                "before": old_status,
                "after": new_status,
                "hard_eligibility": eligibility,
                "target_role_families": target_matches,
                "reason_codes": reason_codes,
            })

    changed_count = len(detailed)
    out_to_in = transitions.get("OUT_OF_SCOPE -> IN_SCOPE", 0)
    aggregate = {
        "active_detailed_jobs_assessed": len(rows),
        "market_status_before": dict(sorted(before.items())),
        "market_status_after": dict(sorted(after.items())),
        "transition_matrix": dict(sorted(transitions.items())),
        "changed_assessments": changed_count,
        "changed_share": round(changed_count / len(rows), 6) if rows else 0.0,
        "changed_employers": dict(sorted(changed_employers.items())),
        "changed_work_modes": dict(sorted(changed_modes.items())),
        "changed_reason_codes": dict(sorted(changed_reasons.items())),
        "changed_geography_completeness": dict(sorted(changed_completeness.items())),
        "changed_target_role_families": dict(sorted(changed_target_families.items())),
        "changed_target_role_match_count": sum(changed_target_families.values()),
        "safety": {
            "out_of_scope_to_in_scope": out_to_in,
            "explicit_compatibility_invented": out_to_in > 0,
        },
        "mews": {
            "active_detailed_jobs": len(mews_rows),
            "before": dict(sorted(Counter(row["before"] for row in mews_rows).items())),
            "after": dict(sorted(Counter(row["after"] for row in mews_rows).items())),
            "stored_work_modes": dict(sorted(Counter(row["stored_work_mode"] for row in mews_rows).items())),
            "effective_work_modes": dict(sorted(Counter(row["effective_work_mode"] for row in mews_rows).items())),
            "city_absent": sum(row["city_absent"] for row in mews_rows),
            "partial_country_reason": sum(
                MarketReasonCode.ACCEPTED_COUNTRY_CITY_UNKNOWN.value in row["reason_codes"]
                for row in mews_rows
            ),
            "market_routed_before": sum(
                row["before"] != "OUT_OF_SCOPE"
                and row["hard_eligibility"] != "INELIGIBLE"
                for row in mews_rows
            ),
            "market_routed_after": sum(
                row["after"] != "OUT_OF_SCOPE"
                and row["hard_eligibility"] != "INELIGIBLE"
                for row in mews_rows
            ),
            "target_role_families": dict(sorted(mews_target_families.items())),
            "target_role_routed_before": sum(
                bool(row["target_role_families"])
                and row["before"] != "OUT_OF_SCOPE"
                and row["hard_eligibility"] != "INELIGIBLE"
                for row in mews_rows
            ),
            "target_role_routed_after": sum(
                bool(row["target_role_families"])
                and row["after"] != "OUT_OF_SCOPE"
                and row["hard_eligibility"] != "INELIGIBLE"
                for row in mews_rows
            ),
            "compatible_semantic_cache_hits": mews_cache_hits,
            "projected_semantic_calls_without_execution": max(0, len(mews_rows) - mews_cache_hits),
        },
        "semantic_assessment_rows": semantic_rows,
    }
    return aggregate, detailed


def _impact_classification(corpus: dict[str, Any]) -> str:
    changed = corpus["changed_assessments"]
    employers = len(corpus["changed_employers"])
    if changed == 0:
        return "NO_EVALUATOR_DEFECT"
    if employers == 1 and set(corpus["changed_employers"]) == {"mews"}:
        return "MEWS_ONLY_EDGE_CASE"
    if corpus["changed_share"] <= 0.05 and employers <= 8:
        return "BOUNDED_MULTI_SOURCE_CORRECTION"
    return "MATERIAL_ROUTING_SEMANTICS_DEFECT"


def run_partial_geography_audit(
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path | None = None,
    *,
    run_id: str | None = None,
    write_artifact: bool = True,
) -> dict[str, Any]:
    config = load_partial_geography_audit_config(config_path)
    raw = config.raw
    database = raw["database_path"]
    database_hash_before = _sha256(database)
    taxonomy = load_taxonomy(raw["taxonomy_path"])
    candidate = load_candidate_profile(raw["candidate_path"], taxonomy)
    frozen = raw["frozen_identity"]
    if candidate.market_access_policy_fingerprint != frozen["market_access_policy_fingerprint"]:
        raise PartialGeographyAuditError("candidate market policy fingerprint changed")
    if candidate.semantic_profile_fingerprint != frozen["semantic_profile_fingerprint"]:
        raise PartialGeographyAuditError("candidate semantic profile fingerprint changed")
    rules = load_market_normalization_rules(raw["market_rules_path"])
    role_config = load_source_portfolio_audit_config(raw["role_audit_config_path"])

    truth_table = _fixture_results(
        raw["truth_table_fixture_path"], candidate, rules, _fixture_job,
    )
    historical = _fixture_results(
        raw["historical_regression_fixture_path"], candidate, rules, _historical_job,
    )
    corpus, detailed = _corpus_replay(
        database, candidate, rules, role_config, str(raw["mews_company_id"]),
    )
    cost = observed_luna_cost(raw["semantic_roi_results_path"])
    projected_calls = corpus["mews"]["projected_semantic_calls_without_execution"]
    corpus["mews"]["projected_semantic_cost_usd"] = round(
        projected_calls * cost["estimated_cost_per_cache_miss_usd"], 8,
    )
    corpus["mews"]["cost_basis"] = cost
    database_hash_after = _sha256(database)
    if database_hash_before != database_hash_after:
        raise PartialGeographyAuditError("read-only audit mutated operational SQLite")
    if not all(item["passed"] for item in truth_table):
        raise PartialGeographyAuditError("truth-table contract failed")
    if not all(item["passed"] for item in historical):
        raise PartialGeographyAuditError("historical market regression failed")
    if corpus["safety"]["out_of_scope_to_in_scope"]:
        raise PartialGeographyAuditError("unexpected OUT_OF_SCOPE to IN_SCOPE transition")

    impact = _impact_classification(corpus)
    run_id = run_id or (
        "partial-geography-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
        + uuid.uuid4().hex[:8]
    )
    result = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment_id": config.experiment_id,
        "experiment_type": EXPERIMENT_TYPE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "truth_table": truth_table,
        "historical_regressions": historical,
        "corpus": corpus,
        "changed_cases": detailed,
        "root_cause": {
            "classification": "MISSING_CITY_TREATED_AS_EXPLICIT_INCOMPATIBILITY",
            "previous_behavior": "A recognized country plus no accepted-city match entered the outside-location branch.",
            "promoted_behavior": "An accepted country with required city absent is UNCERTAIN; explicit incompatible city/country evidence remains OUT_OF_SCOPE.",
            "candidate_policy_changed": False,
        },
        "identity": {
            "previous_evaluator_version": frozen["previous_evaluator_version"],
            "promoted_evaluator_version": EVALUATOR_VERSION,
            "market_normalization_version": rules.normalization_version,
            "market_access_policy_fingerprint": candidate.market_access_policy_fingerprint,
            "semantic_profile_fingerprint": candidate.semantic_profile_fingerprint,
            "audit_config_fingerprint": config.fingerprint,
            "role_classifier_fingerprint": role_config.fingerprint,
            "git": _git_state(),
        },
        "integrity": {
            "database_sha256_before": database_hash_before,
            "database_sha256_after": database_hash_after,
            "database_unchanged": True,
            "sqlite_writes": 0,
            "semantic_calls": 0,
            "semantic_assessment_rows_unchanged": True,
            "candidate_market_policy_changed": False,
            "semantic_profile_changed": False,
        },
        "impact_classification": impact,
        "promotion_decision": "PROMOTE_GENERIC_EVIDENCE_SEMANTICS_CORRECTION",
    }

    if write_artifact:
        root = Path(output_root or raw["outputs"]["root"])
        directory = root / run_id
        directory.mkdir(parents=True, exist_ok=False)
        detailed_path = directory / "audit.json"
        detailed_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        aggregate = {
            key: result[key]
            for key in (
                "schema_version", "run_id", "experiment_id", "experiment_type",
                "created_at", "truth_table", "historical_regressions", "corpus",
                "root_cause", "identity", "integrity", "impact_classification",
                "promotion_decision",
            )
        }
        aggregate["privacy"] = {
            "classification": "REPOSITORY_SAFE_AGGREGATE",
            "private_detailed_artifact_sha256": _sha256(detailed_path),
            "excluded_detail": "PER_JOB_TITLES_LOCATIONS_IDENTITIES_AND_REASON_EVIDENCE",
        }
        aggregate["limitations"] = [
            "The replay covers the current local ACTIVE detailed corpus and is not an unbiased market sample.",
            "The bounded country/city normalizer does not attempt to solve all world geography.",
            "Mews work mode is inferred from generic hybrid wording in current detail evidence; source data does not provide a structured mode.",
            "Target-role overlap is deterministic lexical evidence, not semantic fit.",
            "UNCERTAIN does not establish Prague compatibility and remains capped at REVIEW downstream.",
        ]
        aggregate_path = directory / "aggregate_summary.json"
        aggregate_path.write_text(
            json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        result["artifact_paths"] = {
            "private_detailed": str(detailed_path),
            "repository_safe_aggregate": str(aggregate_path),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only audit of partial country/city market semantics",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-root")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run_partial_geography_audit(
        args.config, args.output_root, run_id=args.run_id,
        write_artifact=not args.dry_run,
    )
    print(json.dumps({
        "run_id": result["run_id"],
        "corpus": result["corpus"],
        "impact_classification": result["impact_classification"],
        "promotion_decision": result["promotion_decision"],
        "semantic_calls": 0,
        "artifact_paths": result.get("artifact_paths"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
