from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.live_validation import current_judgments, load_judgments
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.roi_experiment import load_experiment_config
from opportunity_radar.semantic import SEMANTIC_CONTRACT_VERSION


DECISION_STATUSES = {"PROPOSED", "ACCEPTED", "REJECTED", "SUPERSEDED"}
DECISION_FIELDS = {
    "decision_id", "title", "status", "decided_at", "context", "decision",
    "evidence", "alternatives_rejected", "assumptions", "consequences",
    "supersedes", "related_experiments", "affected_contracts",
}
EXPERIMENT_FIELDS = {
    "experiment_id", "type", "hypothesis", "status", "baseline",
    "intervention", "inputs", "artifacts", "metrics", "result", "decision",
    "limitations", "related_decisions", "commit_or_worktree_state",
}


class ControlPlaneError(ValueError):
    pass


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ControlPlaneError(f"{path}: expected a mapping")
    return value


def load_decision_register(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    raw = _load_yaml(path)
    if raw.get("schema_version") != 1 or not isinstance(raw.get("decisions"), list):
        raise ControlPlaneError(f"{path}: invalid decision-register root")
    seen: set[str] = set()
    for item in raw["decisions"]:
        if not isinstance(item, dict) or set(item) != DECISION_FIELDS:
            raise ControlPlaneError(f"{path}: invalid decision fields")
        decision_id = item["decision_id"]
        if not isinstance(decision_id, str) or not re.fullmatch(r"DR-\d{3}", decision_id):
            raise ControlPlaneError(f"{path}: invalid decision_id {decision_id!r}")
        if decision_id in seen:
            raise ControlPlaneError(f"{path}: duplicate decision_id {decision_id}")
        seen.add(decision_id)
        if item["status"] not in DECISION_STATUSES:
            raise ControlPlaneError(f"{path}: invalid decision status {item['status']}")
        for field in ("evidence", "alternatives_rejected", "assumptions", "consequences", "supersedes", "related_experiments", "affected_contracts"):
            if not isinstance(item[field], list):
                raise ControlPlaneError(f"{path}: {decision_id}.{field} must be a list")
    for item in raw["decisions"]:
        unknown = set(item["supersedes"]) - seen
        if unknown:
            raise ControlPlaneError(f"{path}: unknown superseded decisions {sorted(unknown)}")
    return raw["decisions"]


def load_experiment_registry(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    raw = _load_yaml(path)
    if raw.get("schema_version") != 1 or not isinstance(raw.get("experiments"), list):
        raise ControlPlaneError(f"{path}: invalid experiment-registry root")
    seen: set[str] = set()
    for item in raw["experiments"]:
        if not isinstance(item, dict) or not EXPERIMENT_FIELDS.issubset(item):
            raise ControlPlaneError(f"{path}: invalid experiment fields")
        experiment_id = item["experiment_id"]
        if not isinstance(experiment_id, str) or not experiment_id.startswith("EXP-"):
            raise ControlPlaneError(f"{path}: invalid experiment_id {experiment_id!r}")
        if experiment_id in seen:
            raise ControlPlaneError(f"{path}: duplicate experiment_id {experiment_id}")
        seen.add(experiment_id)
        for field in ("inputs", "artifacts", "related_decisions"):
            if not isinstance(item[field], list):
                raise ControlPlaneError(f"{path}: {experiment_id}.{field} must be a list")
        if not isinstance(item["metrics"], dict):
            raise ControlPlaneError(f"{path}: {experiment_id}.metrics must be a mapping")
    return raw["experiments"]


def validate_control_plane(decisions: list[dict[str, Any]], experiments: list[dict[str, Any]]) -> None:
    decision_ids = {item["decision_id"] for item in decisions}
    experiment_ids = {item["experiment_id"] for item in experiments}
    for decision in decisions:
        unknown = set(decision["related_experiments"]) - experiment_ids
        if unknown:
            raise ControlPlaneError(
                f"{decision['decision_id']}: unknown experiments {sorted(unknown)}"
            )
    for experiment in experiments:
        unknown = set(experiment["related_decisions"]) - decision_ids
        if unknown:
            raise ControlPlaneError(
                f"{experiment['experiment_id']}: unknown decisions {sorted(unknown)}"
            )


def _git_state(root: Path) -> dict[str, Any]:
    def run(*args: str, strip: bool = True) -> str:
        result = subprocess.run(
            ["git", *args], cwd=root, text=True, capture_output=True, check=True,
        )
        return result.stdout.strip() if strip else result.stdout.rstrip("\n")

    try:
        commit = run("rev-parse", "HEAD")
        porcelain = run("status", "--porcelain", strip=False)
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"commit": None, "dirty": None, "changed_paths": [], "error": str(exc)}
    paths = [line[3:] for line in porcelain.splitlines() if len(line) >= 4]
    return {
        "commit": commit,
        "dirty": bool(porcelain),
        "changed_paths": paths,
        "status_fingerprint": hashlib.sha256(porcelain.encode()).hexdigest(),
    }


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _database_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "available": False}
    uri = f"file:{path.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    try:
        result: dict[str, Any] = {
            "path": str(path),
            "available": True,
            "schema_version": connection.execute("PRAGMA user_version").fetchone()[0],
        }
        if _table_exists(connection, "ingestion_runs"):
            latest = connection.execute(
                "SELECT * FROM ingestion_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            result["latest_ingestion_run"] = dict(latest) if latest else None
            result["interrupted_running_count"] = connection.execute(
                "SELECT COUNT(*) FROM ingestion_runs WHERE status='RUNNING'"
            ).fetchone()[0]
        if result.get("latest_ingestion_run") and _table_exists(connection, "source_observations"):
            run_id = result["latest_ingestion_run"]["run_id"]
            sources = connection.execute(
                "SELECT status,inventory_complete,details_complete FROM source_observations WHERE run_id=?",
                (run_id,),
            ).fetchall()
            result["source_health"] = {
                "total": len(sources),
                "status_counts": dict(Counter(row["status"] for row in sources)),
                "inventory_complete": sum(bool(row["inventory_complete"]) for row in sources),
                "details_complete": sum(bool(row["details_complete"]) for row in sources),
                "failed_or_incomplete": sum(
                    row["status"] != "SUCCESS" or not row["inventory_complete"]
                    for row in sources
                ),
            }
        if _table_exists(connection, "job_instances"):
            jobs = connection.execute(
                """SELECT lifecycle_state,COUNT(*) AS n,
                          SUM(CASE WHEN current_fingerprint IS NOT NULL AND latest_observation_id IS NOT NULL THEN 1 ELSE 0 END) AS with_detail
                   FROM job_instances GROUP BY lifecycle_state"""
            ).fetchall()
            result["jobs"] = {
                row["lifecycle_state"].lower(): {
                    "count": row["n"], "with_successful_detail": row["with_detail"] or 0,
                }
                for row in jobs
            }
        if _table_exists(connection, "candidate_profiles"):
            result["candidate_profiles"] = [
                dict(row) for row in connection.execute(
                    """SELECT profile_id,profile_version,full_profile_fingerprint,
                              semantic_profile_fingerprint,scoring_preference_fingerprint
                       FROM candidate_profiles ORDER BY candidate_profile_row_id"""
                ).fetchall()
            ]
        if _table_exists(connection, "semantic_assessments"):
            result["semantic_assessments"] = {
                "count": connection.execute("SELECT COUNT(*) FROM semantic_assessments").fetchone()[0],
                "identities": [
                    dict(row) for row in connection.execute(
                        """SELECT assessor_id,assessor_version,semantic_contract_version,COUNT(*) AS count
                           FROM semantic_assessments
                           GROUP BY assessor_id,assessor_version,semantic_contract_version"""
                    ).fetchall()
                ],
            }
        return result
    finally:
        connection.close()


def _profile_status(root: Path, database: dict[str, Any]) -> dict[str, Any]:
    taxonomy = load_taxonomy(root / "config/taxonomy.yaml")
    profile = load_candidate_profile(root / "config/candidate.yaml", taxonomy)
    persisted = next(
        (
            item for item in database.get("candidate_profiles", [])
            if item["profile_id"] == profile.profile_id
            and item["profile_version"] == profile.version
        ),
        None,
    )
    fingerprint_match = bool(
        persisted
        and persisted["full_profile_fingerprint"] == profile.full_profile_fingerprint
        and persisted["semantic_profile_fingerprint"] == profile.semantic_profile_fingerprint
        and persisted["scoring_preference_fingerprint"] == profile.scoring_preference_fingerprint
    )
    return {
        "profile_id": profile.profile_id,
        "version": profile.version,
        "full_profile_fingerprint": profile.full_profile_fingerprint,
        "semantic_profile_fingerprint": profile.semantic_profile_fingerprint,
        "scoring_preference_fingerprint": profile.scoring_preference_fingerprint,
        "market_access_policy_fingerprint": profile.market_access_policy_fingerprint,
        "persisted_version_found": persisted is not None,
        "config_database_fingerprint_match": fingerprint_match,
    }


def _semantic_status(root: Path) -> dict[str, Any]:
    experiment = load_experiment_config(root / "config/semantic_experiment.yaml")
    model = experiment.models["economical"]
    return {
        "provider": experiment.provider,
        "model": model.model,
        "reasoning_effort": model.reasoning_effort,
        "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
        "configured_assessor_version": f"1:{model.model}",
    }


def _known_blockers(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    collecting = False
    blockers: list[str] = []
    for line in lines:
        if line == "## Known blockers and open decisions":
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if collecting and line.startswith("- "):
            blockers.append(line[2:].strip())
        elif collecting and blockers and line.startswith("  "):
            blockers[-1] += " " + line.strip()
    return blockers


def _validation_metrics(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    match = re.search(r"## Metrics\s+```json\s*(\{.*?\})\s*```", path.read_text(encoding="utf-8"), re.S)
    return json.loads(match.group(1)) if match else None


def _latest_experiment(root: Path, experiments: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    for experiment in experiments:
        for artifact in experiment["artifacts"]:
            if not (root / artifact).exists():
                warnings.append(f"missing_experiment_artifact:{experiment['experiment_id']}:{artifact}")
    completed = [item for item in experiments if item.get("completed_at")]
    latest = max(completed, key=lambda item: item["completed_at"]) if completed else None
    return latest, warnings


def _validation_status(root: Path, experiments: list[dict[str, Any]]) -> dict[str, Any] | None:
    validations = [item for item in experiments if item["type"] == "LIVE_DECISION_VALIDATION"]
    if not validations:
        return None
    experiment = max(validations, key=lambda item: item.get("completed_at", ""))
    batch_path = next((root / item for item in experiment["artifacts"] if item.endswith("/batch.json")), None)
    report_path = next((root / item for item in experiment["artifacts"] if item.endswith("/validation_report.md")), None)
    judgments_path = next((root / item for item in experiment["artifacts"] if item.endswith("judgments.jsonl")), None)
    batch = json.loads(batch_path.read_text(encoding="utf-8")) if batch_path and batch_path.exists() else None
    metrics = _validation_metrics(report_path) if report_path else None
    source = "validation_report"
    reviewed = metrics.get("reviewed") if metrics else None
    if batch and judgments_path and judgments_path.exists():
        reviewed = len(current_judgments(load_judgments(judgments_path), batch["validation_batch_id"]))
        source = "append_only_judgment_log"
    return {
        "experiment_id": experiment["experiment_id"],
        "batch_id": batch.get("validation_batch_id") if batch else None,
        "reviewed": reviewed,
        "sample_size": len(batch["selected_jobs"]) if batch else (metrics.get("sample_size") if metrics else None),
        "verdict": metrics.get("verdict") if metrics else None,
        "completeness_source": source,
        "raw_judgment_log_available": bool(judgments_path and judgments_path.exists()),
    }


def _test_receipt(path: Path, git: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    if not path.exists():
        return None, ["test_receipt_missing"]
    receipt = json.loads(path.read_text(encoding="utf-8"))
    required = {"timestamp", "git_commit", "dirty", "command", "passed", "failed", "deselected"}
    if not required.issubset(receipt):
        raise ControlPlaneError(f"{path}: invalid test receipt")
    if receipt["git_commit"] != git.get("commit") or receipt["dirty"] != git.get("dirty"):
        warnings.append("test_receipt_git_state_mismatch")
    if receipt.get("git_status_fingerprint") and receipt["git_status_fingerprint"] != git.get("status_fingerprint"):
        warnings.append("test_receipt_worktree_mismatch")
    return receipt, warnings


def collect_project_status(root: str | Path = ".", now: datetime | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    decisions = load_decision_register(root / "docs/decisions.yaml")
    experiments = load_experiment_registry(root / "experiments/registry.yaml")
    validate_control_plane(decisions, experiments)
    git = _git_state(root)
    database = _database_status(root / "output/opportunity_radar.sqlite3")
    candidate = _profile_status(root, database)
    semantic = _semantic_status(root)
    latest_experiment, artifact_warnings = _latest_experiment(root, experiments)
    validation = _validation_status(root, experiments)
    receipt, receipt_warnings = _test_receipt(root / "output/test_receipt.json", git)
    warnings = [*artifact_warnings, *receipt_warnings]
    if git.get("dirty"):
        warnings.append("working_tree_dirty")
    latest_run = database.get("latest_ingestion_run")
    current_time = now or datetime.now(timezone.utc)
    if latest_run:
        started = datetime.fromisoformat(latest_run["started_at"])
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if (current_time - started.astimezone(timezone.utc)).days >= 7:
            warnings.append("latest_ingestion_run_older_than_7_days")
        if latest_run["status"] != "COMPLETED":
            warnings.append(f"latest_ingestion_run_{latest_run['status'].lower()}")
    if database.get("interrupted_running_count"):
        warnings.append("interrupted_running_rows_present")
    if not candidate["config_database_fingerprint_match"]:
        warnings.append("candidate_config_database_fingerprint_mismatch")
    if validation and validation["reviewed"] != validation["sample_size"]:
        warnings.append("latest_validation_incomplete")
    return {
        "generated_at": current_time.astimezone(timezone.utc).isoformat(),
        "derived_read_only": True,
        "git": git,
        "database": database,
        "candidate": candidate,
        "semantic": semantic,
        "latest_experiment": {
            key: latest_experiment.get(key) for key in
            ("experiment_id", "type", "status", "completed_at", "result", "decision")
        } if latest_experiment else None,
        "latest_validation": validation,
        "decision_count": len(decisions),
        "experiment_count": len(experiments),
        "known_blockers": _known_blockers(root / "docs/STATUS.md"),
        "last_test_receipt": receipt,
        "staleness_warnings": sorted(set(warnings)),
    }


def render_markdown(status: dict[str, Any]) -> str:
    db = status["database"]
    latest = db.get("latest_ingestion_run") or {}
    sources = db.get("source_health") or {}
    jobs = db.get("jobs") or {}
    validation = status.get("latest_validation") or {}
    tests = status.get("last_test_receipt")
    lines = [
        "# Opportunity Radar — Derived Project Status", "",
        f"Generated: {status['generated_at']}",
        f"Git: `{status['git'].get('commit')}` · dirty={status['git'].get('dirty')}",
        f"SQLite: available={db.get('available')} · schema={db.get('schema_version')}",
        f"Latest ingestion: `{latest.get('run_id')}` · {latest.get('status')}",
        f"Sources: {sources.get('total', 0)} · statuses={json.dumps(sources.get('status_counts', {}), sort_keys=True)} · details_complete={sources.get('details_complete', 0)}",
        f"Jobs: active={jobs.get('active', {}).get('count', 0)} · closed={jobs.get('closed', {}).get('count', 0)}",
        f"Candidate: `{status['candidate']['profile_id']}` v{status['candidate']['version']} · database_match={status['candidate']['config_database_fingerprint_match']}",
        f"Semantic: `{status['semantic']['model']}` · reasoning={status['semantic']['reasoning_effort']} · contract=`{status['semantic']['semantic_contract_version']}` · assessments={db.get('semantic_assessments', {}).get('count', 0)}",
        f"Latest validation: `{validation.get('batch_id')}` · reviewed={validation.get('reviewed')}/{validation.get('sample_size')} · verdict={validation.get('verdict')}",
        f"Registry: {status['experiment_count']} experiments · {status['decision_count']} decisions", "",
        "## Test receipt", "",
        (f"{tests['passed']} passed, {tests['failed']} failed, {tests['deselected']} deselected · `{tests['command']}` · {tests['timestamp']}" if tests else "No local test receipt available."), "",
        "## Known blockers", "",
        *[f"- {item}" for item in status["known_blockers"]], "",
        "## Warnings", "",
        *([f"- `{item}`" for item in status["staleness_warnings"]] or ["- None"]), "",
        "> This output is derived and replaceable. `docs/STATUS.md` is the handoff authority.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Opportunity Radar project health")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    output.add_argument("--markdown", action="store_true", help="emit human-readable Markdown")
    parser.add_argument("--root", default=".", help=argparse.SUPPRESS)
    args = parser.parse_args()
    status = collect_project_status(args.root)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(status), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
