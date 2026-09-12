from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

import opportunity_radar.wave_a_preflight as preflight
from opportunity_radar.models import JobLocation, JobReference, ListingFacts
from opportunity_radar.wave_a_preflight import BoundedSession, RequestBudgetExceeded, WaveAPreflightError, load_wave_a_preflight_config, run_wave_a_preflight


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/wave_a_source_preflight_v1.yaml"


def test_config_has_exact_wave_a_and_is_separate_from_production():
    config = load_wave_a_preflight_config(CONFIG)
    ids = [item["company_id"] for item in config.sources]
    assert ids == ["keboola", "mews", "productboard", "commerzbank", "erste_group", "abb", "kpmg", "msd", "zentiva"]
    production = {item.company_id for item in preflight.load_companies(ROOT / "config/companies.yaml")}
    assert production.intersection(ids) == {"keboola", "commerzbank", "kpmg"}


def test_request_guard_blocks_detail_graphql_and_enforces_cap(monkeypatch):
    session = BoundedSession(1, 1, 1)
    with pytest.raises(WaveAPreflightError, match="detail request blocked"):
        session.post("https://example.test/api", json={"query": "query($jobAdId: ID!) { jobAd(id: $jobAdId) { id } }"})
    class Response:
        url = "https://example.test/jobs"
        status_code = 200
    monkeypatch.setattr("requests.Session.request", lambda *_args, **_kwargs: Response())
    session.get("https://example.test/jobs")
    with pytest.raises(RequestBudgetExceeded):
        session.get("https://example.test/jobs")


def test_nested_json_contract_flattens_groups_and_validates_counts():
    class Response:
        status_code = 200
        url = "https://example.test/api/careers"
        def raise_for_status(self): pass
        def json(self):
            return [{"name": "Product", "jobCount": 1, "jobs": [{
                "id": 7, "title": "Product Analyst", "url": "https://example.test/jobs/7",
                "location": "Prague", "locations": ["Prague"], "updatedAt": "2026-09-10T12:00:00Z",
            }]}]
    class Session:
        def get(self, _url): return Response()
    item = load_wave_a_preflight_config(CONFIG).sources[1]
    refs, diagnostic = preflight._nested_json_references(item, preflight._company_config(item), Session())
    assert len(refs) == 1
    assert refs[0].listing_facts.title == "Product Analyst"
    assert refs[0].listing_facts.locations[0].raw == "Prague"
    assert diagnostic == {"group_count": 1, "group_counts_validated": True}


def test_metrics_preserve_unknown_market_and_title_only_roles():
    scope = preflight.load_market_scope(ROOT / "config/market_scope.yaml")
    roles = preflight.load_source_portfolio_audit_config(ROOT / "experiments/source_portfolio_audit_v1.yaml")
    refs = [JobReference("x", "1", "https://example.test/1", listing_facts=ListingFacts(title="Product Analyst", locations=(JobLocation("Prague"),)))]
    metrics = preflight._listing_metrics(refs, scope, roles)
    assert metrics["market_scope_counts"] == {"SELECT_IN_SCOPE": 1}
    assert metrics["role_family_title_counts"]["PRODUCT_STRATEGY"] == 1
    assert metrics["duplicate_external_id_count"] == 0
    unknown = [JobReference("x", "2", "https://example.test/2", listing_facts=ListingFacts(title="Program Lead"))]
    assert preflight._listing_metrics(unknown, scope, roles)["market_scope_counts"] == {"SELECT_GEOGRAPHY_UNKNOWN": 1}
    extension = load_wave_a_preflight_config(CONFIG).raw["role_extension"]
    adjacent = [JobReference("x", "3", "https://example.test/3", listing_facts=ListingFacts(title="Project Manager - Financial Intelligence"))]
    assert preflight._listing_metrics(adjacent, scope, roles, extension)["role_family_title_counts"]["DECISION_INTELLIGENCE_SUPPORT"] == 1


def _database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
      PRAGMA user_version=3;
      CREATE TABLE ingestion_runs (run_id TEXT);
      CREATE TABLE source_observations (source_observation_id INTEGER);
      CREATE TABLE job_instances (job_instance_id INTEGER);
      CREATE TABLE job_observations (job_observation_id INTEGER);
      CREATE TABLE events (event_id INTEGER);
      CREATE TABLE semantic_assessments (semantic_assessment_id INTEGER);
    """)
    connection.commit()
    connection.close()


def test_full_runner_is_zero_detail_read_only_and_aggregate_is_sanitized(tmp_path, monkeypatch):
    source = load_wave_a_preflight_config(CONFIG)
    companies = tmp_path / "companies.yaml"
    companies.write_text("companies: []\n", encoding="utf-8")
    database = tmp_path / "state.sqlite3"
    _database(database)
    raw = dict(source.raw)
    raw["companies_path"] = str(companies)
    raw["database_path"] = str(database)
    raw["market_scope_path"] = str(ROOT / "config/market_scope.yaml")
    raw["role_audit_config_path"] = str(ROOT / "experiments/source_portfolio_audit_v1.yaml")
    config_path = tmp_path / "preflight.yaml"
    import yaml
    config_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    class Adapter:
        def __init__(self): self.session = None
        def list_jobs(self, company):
            return [JobReference(company.company_id, "1", f"https://example.test/{company.company_id}/1", listing_facts=ListingFacts(title="Business Analyst", locations=(JobLocation("Prague"),)))]
        def fetch_job(self, _ref): raise AssertionError("detail retrieval must never be called")
    monkeypatch.setattr(preflight.AdapterRegistry, "create", lambda _company: Adapter())
    monkeypatch.setattr(preflight, "_alma_credentials", lambda *_: ("widget", "key", "/detail"))
    monkeypatch.setattr(preflight, "_nested_json_references", lambda item, company, session: (Adapter().list_jobs(company), {"group_count": 1, "group_counts_validated": True}))
    class Response:
        url = "https://example.test/"
        status_code = 200
        text = ""
        def raise_for_status(self): pass
    monkeypatch.setattr(BoundedSession, "get", lambda self, _url: Response())
    before = database.read_bytes()
    result = run_wave_a_preflight(config_path, tmp_path / "output", "offline")
    assert database.read_bytes() == before
    assert result["integrity"]["semantic_calls"] == 0
    assert result["integrity"]["detail_calls"] == 0
    aggregate = json.loads(Path(result["artifact_paths"]["repository_safe_aggregate"]).read_text())
    serialized = json.dumps(aggregate)
    assert "private_rows" not in serialized
    assert "example.test" not in serialized
    assert aggregate["integrity"]["database_byte_identical"] is True
    assert hashlib.sha256(database.read_bytes()).hexdigest() == aggregate["integrity"]["database_sha256_after"]
