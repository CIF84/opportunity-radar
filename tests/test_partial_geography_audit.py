from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from opportunity_radar.models import JobLocation, JobReference, NormalizedJob, WorkMode
from opportunity_radar.partial_geography_audit import (
    PartialGeographyAuditError,
    load_partial_geography_audit_config,
    run_partial_geography_audit,
)
from opportunity_radar.state_models import DetailObservation, SourceOutcome
from opportunity_radar.state_repository import StateRepository


ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "experiments/partial_geography_semantics_v1.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized(
    company_id: str,
    external_id: str,
    raw_location: str,
    city: str | None,
    country: str | None,
    work_mode: WorkMode,
    description: str,
) -> NormalizedJob:
    return NormalizedJob(
        company_id=company_id,
        company_name=company_id.title(),
        external_job_id=external_id,
        title=f"Fixture role {external_id}",
        locations=[JobLocation(raw_location, city, None, country)],
        work_mode=work_mode,
        canonical_url=f"https://example.test/{company_id}/{external_id}",
        description=description,
        employment_type=None,
        department=None,
        date_posted=None,
        valid_through=None,
        source="fixture",
        retrieved_at=datetime(2026, 9, 12, tzinfo=timezone.utc),
    )


def _database(path: Path) -> None:
    jobs = [
        _normalized(
            "mews", "partial", "Czechia; Spain", None, None,
            WorkMode.UNSPECIFIED, "Flexible, hybrid working options.",
        ),
        _normalized(
            "fixture", "brno", "Brno, Czechia", "Brno", "Czechia",
            WorkMode.HYBRID, "Role duties.",
        ),
        _normalized(
            "fixture", "germany", "Germany", None, "Germany",
            WorkMode.HYBRID, "Role duties.",
        ),
        _normalized(
            "fixture", "prague", "Prague, Czechia", "Prague", "Czechia",
            WorkMode.ONSITE, "Role duties.",
        ),
    ]
    repository = StateRepository(path)
    repository.create_run("audit-fixture", "2026-09-12T00:00:00+00:00")
    for company_id in ("mews", "fixture"):
        selected = [job for job in jobs if job.company_id == company_id]
        references = [
            JobReference(job.company_id, job.external_job_id, job.canonical_url)
            for job in selected
        ]
        outcome = SourceOutcome(
            company_id, company_id.title(), "fixture", "SUCCESS",
            datetime(2026, 9, 12, tzinfo=timezone.utc), references,
            [DetailObservation(reference, job) for reference, job in zip(references, selected)],
            True, True, len(references),
        )
        repository.apply_outcome("audit-fixture", outcome)


def _config(tmp_path: Path, database: Path) -> Path:
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    raw["database_path"] = str(database)
    for key in (
        "specification", "candidate_path", "taxonomy_path", "market_rules_path",
        "role_audit_config_path", "truth_table_fixture_path",
        "historical_regression_fixture_path", "semantic_roi_results_path",
    ):
        raw[key] = str(ROOT / raw[key])
    raw["outputs"]["root"] = str(tmp_path / "output")
    path = tmp_path / "audit.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def test_config_freezes_policy_and_evaluator_identity():
    config = load_partial_geography_audit_config(CONFIG)
    assert config.experiment_id == "EXP-PARTIAL-GEOGRAPHY-001"
    assert config.raw["frozen_identity"] == {
        "previous_evaluator_version": "phase4-current-candidate-market-v2",
        "promoted_evaluator_version": "phase4-current-candidate-market-v3",
        "market_access_policy_fingerprint": "86c00d7cfb8b40b02c141b955ce482575464396a3097065fd435e64d11411bdb",
        "semantic_profile_fingerprint": "6579b21e2bc22fef927ca17bdf6083b7e9a099bd5810b49528f589c83793819b",
    }


def test_read_only_replay_promotes_only_partial_country_semantics(tmp_path, monkeypatch):
    database = tmp_path / "state.sqlite3"
    _database(database)
    config = _config(tmp_path, database)
    before = _sha256(database)
    monkeypatch.setattr(
        "opportunity_radar.semantic.DeterministicSemanticAssessor.assess",
        lambda *args, **kwargs: pytest.fail("partial-geography audit must not call semantics"),
    )
    result = run_partial_geography_audit(
        config, run_id="partial-geography-test", write_artifact=False,
    )
    assert result["corpus"]["transition_matrix"] == {
        "IN_SCOPE -> IN_SCOPE": 1,
        "OUT_OF_SCOPE -> OUT_OF_SCOPE": 2,
        "OUT_OF_SCOPE -> UNCERTAIN": 1,
    }
    assert result["corpus"]["safety"] == {
        "out_of_scope_to_in_scope": 0,
        "explicit_compatibility_invented": False,
    }
    assert result["corpus"]["mews"]["before"] == {"OUT_OF_SCOPE": 1}
    assert result["corpus"]["mews"]["after"] == {"UNCERTAIN": 1}
    assert result["impact_classification"] == "MEWS_ONLY_EDGE_CASE"
    assert result["integrity"]["semantic_calls"] == 0
    assert _sha256(database) == before


def test_written_aggregate_excludes_private_per_job_evidence(tmp_path):
    database = tmp_path / "state.sqlite3"
    _database(database)
    config = _config(tmp_path, database)
    result = run_partial_geography_audit(
        config, run_id="partial-geography-output-test", write_artifact=True,
    )
    aggregate = json.loads(
        Path(result["artifact_paths"]["repository_safe_aggregate"]).read_text(
            encoding="utf-8",
        )
    )
    detailed = json.loads(
        Path(result["artifact_paths"]["private_detailed"]).read_text(encoding="utf-8")
    )
    assert "changed_cases" not in aggregate
    assert detailed["changed_cases"][0]["title"]
    assert aggregate["privacy"]["classification"] == "REPOSITORY_SAFE_AGGREGATE"


def test_repository_ignores_detail_but_allows_sanitized_aggregate():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "output/partial_geography_semantics/**/*" in ignore
    assert "!output/partial_geography_semantics/**/aggregate_summary.json" in ignore


def test_config_rejects_policy_fingerprint_drift(tmp_path):
    database = tmp_path / "state.sqlite3"
    _database(database)
    valid = _config(tmp_path, database)
    raw = deepcopy(yaml.safe_load(valid.read_text(encoding="utf-8")))
    raw["frozen_identity"]["market_access_policy_fingerprint"] = "changed"
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(PartialGeographyAuditError, match="market policy fingerprint changed"):
        run_partial_geography_audit(path, write_artifact=False)
