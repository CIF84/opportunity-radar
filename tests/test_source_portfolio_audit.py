from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import opportunity_radar.source_portfolio_audit as audit
from opportunity_radar.source_portfolio_audit import (
    OTHER_FAMILY,
    classify_role_families,
    concentration_metrics,
    load_source_portfolio_audit_config,
    run_source_portfolio_audit,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/source_portfolio_audit_v1.yaml"


def _config():
    return load_source_portfolio_audit_config(CONFIG)


def _families(title: str, description: str = "") -> set[str]:
    return {item.family for item in classify_role_families(title, description, _config())}


def test_source_portfolio_config_is_bounded_and_resolves_research_companies():
    config = load_source_portfolio_audit_config(CONFIG)
    assert config.experiment_id == "EXP-SOURCE-PORTFOLIO-001"
    assert len(config.raw["candidate_employers"]) == 30
    longlist = audit._candidate_longlist(config)
    assert longlist["longlist_count"] == 30
    assert len(longlist["wave_a"]) + longlist["production_configured_candidate_count"] == 9
    assert len(longlist["wave_b"]) == 10


def test_concentration_metrics_are_reproducible():
    result = concentration_metrics({"a": 50, "b": 30, "c": 20, "zero": 0})
    assert result == {
        "total": 100,
        "employer_count": 3,
        "top_1_share": 0.5,
        "top_3_share": 1.0,
        "top_5_share": 1.0,
        "hhi": 3800.0,
        "effective_employers": 2.632,
    }


def test_analyst_title_variants_are_covered_without_company_logic():
    assert "BUSINESS_ANALYTICS" in _families("Senior Business Analyst")
    assert "DATA_ANALYTICS" in _families("Data Analyst")
    assert "DECISION_INTELLIGENCE_SUPPORT" in _families("Insights Analyst")
    assert "COMMERCIAL_PRICING_RETENTION" in _families("Commercial Analyst")
    assert "BUSINESS_REVENUE_OPERATIONS" in _families("Revenue Operations Analyst")
    assert "PRODUCT_STRATEGY" in _families("Product Analyst")
    assert "DECISION_INTELLIGENCE_SUPPORT" in _families("Decision Scientist")
    source = inspect.getsource(classify_role_families)
    assert "company" not in source.casefold()


def test_description_requires_two_independent_signals():
    one = classify_role_families(
        "Program Lead", "Provides business intelligence for stakeholders.", _config(),
    )
    assert "BUSINESS_ANALYTICS" not in {item.family for item in one}
    two = classify_role_families(
        "Program Lead",
        "Provides business intelligence and actionable insights for stakeholders.",
        _config(),
    )
    match = next(item for item in two if item.family == "BUSINESS_ANALYTICS")
    assert match.evidence_level == "DESCRIPTION_SUPPORTED"


def test_ambiguous_role_is_not_forced_into_a_family():
    result = classify_role_families(
        "Program Lead", "Coordinate stakeholders and maintain plans.", _config(),
    )
    assert [item.family for item in result] == [OTHER_FAMILY]


def test_role_classification_is_neutral_and_can_be_multilabel():
    result = classify_role_families(
        "Product Analyst",
        "Use business intelligence and actionable insights to guide the product roadmap.",
        _config(),
    )
    families = {item.family for item in result}
    assert {"PRODUCT_STRATEGY", "BUSINESS_ANALYTICS"} <= families
    assert all("positive" not in item.evidence_level.casefold() for item in result)


def _empty_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA user_version=3;
        CREATE TABLE ingestion_runs (
          run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT, status TEXT NOT NULL
        );
        CREATE TABLE source_observations (
          source_observation_id INTEGER PRIMARY KEY, run_id TEXT NOT NULL,
          company_id TEXT NOT NULL, adapter TEXT NOT NULL, status TEXT NOT NULL,
          expected_count INTEGER, observed_count INTEGER NOT NULL,
          inventory_complete INTEGER NOT NULL, details_complete INTEGER NOT NULL,
          detail_success_count INTEGER NOT NULL, detail_failure_count INTEGER NOT NULL,
          error_type TEXT, error_message TEXT, observed_at TEXT NOT NULL
        );
        CREATE TABLE job_instances (
          job_instance_id INTEGER PRIMARY KEY, company_id TEXT NOT NULL,
          canonical_url TEXT NOT NULL, current_fingerprint TEXT,
          latest_observation_id INTEGER, lifecycle_state TEXT NOT NULL
        );
        CREATE TABLE job_observations (
          job_observation_id INTEGER PRIMARY KEY, run_id TEXT NOT NULL,
          job_instance_id INTEGER NOT NULL, fingerprint TEXT NOT NULL,
          normalized_snapshot TEXT
        );
        """
    )
    connection.commit()
    connection.close()


def test_full_audit_is_read_only_and_aggregate_omits_private_examples(tmp_path, monkeypatch):
    database = tmp_path / "state.sqlite3"
    _empty_database(database)
    metadata = {
        "active_job_count": 0,
        "active_usable_detail_count": 0,
        "unassessable_detail_count": 0,
        "cluster_count": 0,
        "normal_candidate_count": 0,
        "market_status_counts": {},
        "cache_status_counts": {},
        "latest_ingestion_run": None,
        "source_failures_or_incomplete": [],
        "candidate": {},
        "semantic": {},
    }
    monkeypatch.setattr(audit, "build_current_cluster_population", lambda *_: ([], metadata))
    before = database.read_bytes()
    result = run_source_portfolio_audit(
        CONFIG, database, tmp_path / "artifacts", run_id="test-audit",
    )
    assert database.read_bytes() == before
    aggregate = json.loads(Path(
        result["artifact_paths"]["repository_safe_aggregate"]
    ).read_text())
    assert "role_examples" not in aggregate
    assert aggregate["integrity"]["sqlite_writes"] == 0
    assert aggregate["integrity"]["semantic_calls"] == 0
    assert aggregate["privacy"]["excluded_detail"] == (
        "PER_CLUSTER_TITLES_AND_CLASSIFICATION_SIGNALS"
    )
