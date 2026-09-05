from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.project_status import (
    collect_project_status,
    load_decision_register,
    load_experiment_registry,
    main,
    render_markdown,
    validate_control_plane,
)


ROOT = Path(__file__).parents[1]


def test_repository_decision_and_experiment_registries_are_valid():
    decisions = load_decision_register(ROOT / "docs/decisions.yaml")
    experiments = load_experiment_registry(ROOT / "experiments/registry.yaml")
    validate_control_plane(decisions, experiments)
    assert len(decisions) >= 16
    assert {item["experiment_id"] for item in experiments} >= {
        "EXP-INGESTION-001", "EXP-STATE-001", "EXP-PHASE3-001",
        "EXP-SEMANTIC-ROI-001", "EXP-SCOPE-001", "EXP-DETAIL-REUSE-001",
        "EXP-LIVE-VALIDATION-001",
    }


def _write_control_plane(root: Path, include_judgments: bool = True) -> Path:
    (root / "docs").mkdir()
    (root / "experiments").mkdir()
    (root / "config").mkdir()
    (root / "output/live_validation/batch-test").mkdir(parents=True)
    (root / "data/live_validation").mkdir(parents=True)
    for name in ("candidate.yaml", "taxonomy.yaml", "semantic_experiment.yaml"):
        shutil.copy(ROOT / "config" / name, root / "config" / name)

    (root / "docs/STATUS.md").write_text(
        "# Status\n\n## Known blockers and open decisions\n\n"
        "- First blocker.\n- Second blocker with\n  continued detail.\n\n## Next\n",
        encoding="utf-8",
    )
    decisions = {
        "schema_version": 1,
        "decisions": [{
            "decision_id": "DR-001", "title": "Test", "status": "ACCEPTED",
            "decided_at": "2026-09-04", "context": "Context", "decision": "Decision",
            "evidence": [], "alternatives_rejected": [], "assumptions": [],
            "consequences": [], "supersedes": [], "related_experiments": ["EXP-TEST"],
            "affected_contracts": [],
        }],
    }
    (root / "docs/decisions.yaml").write_text(
        __import__("yaml").safe_dump(decisions, sort_keys=False), encoding="utf-8"
    )
    artifacts = [
        "output/live_validation/batch-test/batch.json",
        "output/live_validation/batch-test/validation_report.md",
        "data/live_validation/judgments.jsonl",
    ]
    experiments = {
        "schema_version": 1,
        "experiments": [{
            "experiment_id": "EXP-TEST", "type": "LIVE_DECISION_VALIDATION",
            "hypothesis": "Test hypothesis", "status": "COMPLETED",
            "completed_at": "2026-09-04", "baseline": "Baseline",
            "intervention": "Intervention", "inputs": [], "artifacts": artifacts,
            "metrics": {"reviewed": 2}, "result": "Result", "decision": "NO_GO",
            "limitations": "Directional", "related_decisions": ["DR-001"],
            "commit_or_worktree_state": "test",
        }],
    }
    (root / "experiments/registry.yaml").write_text(
        __import__("yaml").safe_dump(experiments, sort_keys=False), encoding="utf-8"
    )
    batch = {
        "validation_batch_id": "batch-test",
        "selected_jobs": [
            {"job_instance_id": 10, "review_number": 1},
            {"job_instance_id": 20, "review_number": 2},
        ],
    }
    (root / artifacts[0]).write_text(json.dumps(batch), encoding="utf-8")
    metrics = {"reviewed": 2, "sample_size": 2, "verdict": "NO_GO"}
    (root / artifacts[1]).write_text(
        "# Report\n\n## Metrics\n\n```json\n" + json.dumps(metrics) + "\n```\n",
        encoding="utf-8",
    )
    if include_judgments:
        records = [
            {"judgment_id": "j1", "validation_batch_id": "batch-test", "job_instance_id": 10, "supersedes_judgment_id": None},
            {"judgment_id": "j2", "validation_batch_id": "batch-test", "job_instance_id": 20, "supersedes_judgment_id": None},
        ]
        (root / artifacts[2]).write_text(
            "".join(json.dumps(item) + "\n" for item in records), encoding="utf-8"
        )

    taxonomy = load_taxonomy(root / "config/taxonomy.yaml")
    profile = load_candidate_profile(root / "config/candidate.yaml", taxonomy)
    database = root / "output/opportunity_radar.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript("""
            PRAGMA user_version=3;
            CREATE TABLE ingestion_runs(run_id TEXT,started_at TEXT,completed_at TEXT,status TEXT);
            CREATE TABLE source_observations(run_id TEXT,status TEXT,inventory_complete INTEGER,details_complete INTEGER);
            CREATE TABLE job_instances(lifecycle_state TEXT,current_fingerprint TEXT,latest_observation_id INTEGER);
            CREATE TABLE candidate_profiles(profile_id TEXT,profile_version INTEGER,full_profile_fingerprint TEXT,semantic_profile_fingerprint TEXT,scoring_preference_fingerprint TEXT,candidate_profile_row_id INTEGER);
            CREATE TABLE semantic_assessments(assessor_id TEXT,assessor_version TEXT,semantic_contract_version TEXT);
        """)
        connection.execute(
            "INSERT INTO ingestion_runs VALUES (?,?,?,?)",
            ("run-1", "2026-09-04T00:00:00+00:00", "2026-09-04T00:01:00+00:00", "COMPLETED"),
        )
        connection.executemany(
            "INSERT INTO source_observations VALUES (?,?,?,?)",
            [("run-1", "SUCCESS", 1, 1), ("run-1", "SUCCESS", 1, 0)],
        )
        connection.executemany(
            "INSERT INTO job_instances VALUES (?,?,?)",
            [("ACTIVE", "a", 1), ("CLOSED", "b", 2)],
        )
        connection.execute(
            "INSERT INTO candidate_profiles VALUES (?,?,?,?,?,?)",
            (profile.profile_id, profile.version, profile.full_profile_fingerprint,
             profile.semantic_profile_fingerprint, profile.scoring_preference_fingerprint, 1),
        )
        connection.execute(
            "INSERT INTO semantic_assessments VALUES (?,?,?)",
            ("external-structured", "1:gpt-5.6-luna", "phase3-semantic-v1"),
        )
    return database


def test_status_is_read_only_and_detects_complete_latest_validation(tmp_path):
    database = _write_control_plane(tmp_path)
    profile = load_candidate_profile(
        tmp_path / "config/candidate.yaml",
        load_taxonomy(tmp_path / "config/taxonomy.yaml"),
    )
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    modified = database.stat().st_mtime_ns
    status = collect_project_status(
        tmp_path, now=datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    )
    after = hashlib.sha256(database.read_bytes()).hexdigest()
    assert before == after
    assert database.stat().st_mtime_ns == modified
    assert status["derived_read_only"] is True
    assert status["database"]["schema_version"] == 3
    assert status["database"]["source_health"]["total"] == 2
    assert status["candidate"]["config_database_fingerprint_match"] is True
    assert status["candidate"]["market_access_policy_fingerprint"] == profile.market_access_policy_fingerprint
    assert status["candidate"]["decision_preference_fingerprint"] == profile.decision_preference_fingerprint
    assert status["latest_validation"] == {
        "experiment_id": "EXP-TEST", "batch_id": "batch-test", "reviewed": 2,
        "sample_size": 2, "verdict": "NO_GO",
        "completeness_source": "append_only_judgment_log",
        "raw_judgment_log_available": True,
    }
    assert status["known_blockers"] == [
        "First blocker.", "Second blocker with continued detail."
    ]
    assert "latest_validation_incomplete" not in status["staleness_warnings"]
    assert "# Opportunity Radar — Derived Project Status" in render_markdown(status)


def test_status_can_use_derived_report_when_private_judgments_are_absent(tmp_path):
    _write_control_plane(tmp_path, include_judgments=False)
    status = collect_project_status(
        tmp_path, now=datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    )
    assert status["latest_validation"]["reviewed"] == 2
    assert status["latest_validation"]["completeness_source"] == "validation_report"
    assert status["latest_validation"]["raw_judgment_log_available"] is False
    assert any(
        item.startswith("missing_experiment_artifact:EXP-TEST:data/live_validation")
        for item in status["staleness_warnings"]
    )


def test_status_cli_emits_json_and_markdown(tmp_path, monkeypatch, capsys):
    _write_control_plane(tmp_path)
    monkeypatch.setattr(sys, "argv", ["opportunity-radar-status", "--root", str(tmp_path), "--json"])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["derived_read_only"] is True

    monkeypatch.setattr(sys, "argv", ["opportunity-radar-status", "--root", str(tmp_path), "--markdown"])
    assert main() == 0
    assert "# Opportunity Radar — Derived Project Status" in capsys.readouterr().out
