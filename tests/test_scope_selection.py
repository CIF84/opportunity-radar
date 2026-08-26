from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from opportunity_radar.models import JobLocation, JobReference, ListingFacts, WorkMode
from opportunity_radar.scope_measurement import run_scope_measurement
from opportunity_radar.scope_selection import (
    SelectionDecision, listing_facts_fingerprint, load_market_scope, select_for_detail,
)


SCOPE = load_market_scope("config/market_scope.yaml")


@pytest.mark.parametrize(
    "facts,decision,reason",
    [
        (ListingFacts(locations=(JobLocation("Czechia", country="Czechia"),)), SelectionDecision.SELECT_IN_SCOPE, "LISTING_GEOGRAPHY_COMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Česká republika", country="Česká republika"),)), SelectionDecision.SELECT_IN_SCOPE, "LISTING_GEOGRAPHY_COMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Prague"),)), SelectionDecision.SELECT_IN_SCOPE, "LISTING_GEOGRAPHY_COMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Berlin, Germany", country="Germany"),), work_mode=WorkMode.ONSITE), SelectionDecision.SKIP_EXPLICITLY_OUT_OF_SCOPE, "ALL_LISTING_LOCATIONS_EXPLICITLY_INCOMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Munich, Germany", country="Germany"),), work_mode=WorkMode.HYBRID), SelectionDecision.SKIP_EXPLICITLY_OUT_OF_SCOPE, "ALL_LISTING_LOCATIONS_EXPLICITLY_INCOMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Mumbai, India"),)), SelectionDecision.SKIP_EXPLICITLY_OUT_OF_SCOPE, "ALL_LISTING_LOCATIONS_EXPLICITLY_INCOMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Bengaluru, KA, IN, 560001"),)), SelectionDecision.SKIP_EXPLICITLY_OUT_OF_SCOPE, "ALL_LISTING_LOCATIONS_EXPLICITLY_INCOMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Prague 1 - Nove Mesto, CZ, 110 00"),)), SelectionDecision.SELECT_IN_SCOPE, "LISTING_GEOGRAPHY_COMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Den Haag, NL, 2596 CZ"),)), SelectionDecision.SKIP_EXPLICITLY_OUT_OF_SCOPE, "ALL_LISTING_LOCATIONS_EXPLICITLY_INCOMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Prague, CZ, 110 00 +1 more…"),)), SelectionDecision.SELECT_GEOGRAPHY_UNKNOWN, "LISTING_GEOGRAPHY_MISSING_OR_UNPARSED"),
        (ListingFacts(locations=(JobLocation("Remote, Germany"),), work_mode=WorkMode.REMOTE), SelectionDecision.SELECT_REMOTE_ELIGIBILITY_UNKNOWN, "REMOTE_GEOGRAPHIC_ELIGIBILITY_NOT_PROVEN_INCOMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Remote - Global"),), work_mode=WorkMode.REMOTE), SelectionDecision.SELECT_IN_SCOPE, "REMOTE_REGION_COMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Remote - Europe / EU"),), work_mode=WorkMode.REMOTE), SelectionDecision.SELECT_IN_SCOPE, "REMOTE_REGION_COMPATIBLE"),
        (ListingFacts(work_mode=WorkMode.REMOTE), SelectionDecision.SELECT_REMOTE_ELIGIBILITY_UNKNOWN, "REMOTE_GEOGRAPHIC_ELIGIBILITY_NOT_PROVEN_INCOMPATIBLE"),
        (ListingFacts(), SelectionDecision.SELECT_GEOGRAPHY_UNKNOWN, "LISTING_GEOGRAPHY_MISSING_OR_UNPARSED"),
        (ListingFacts(locations=(JobLocation("2 Locations"),)), SelectionDecision.SELECT_GEOGRAPHY_UNKNOWN, "LISTING_GEOGRAPHY_MISSING_OR_UNPARSED"),
        (ListingFacts(locations=(JobLocation("Prague"), JobLocation("Unknown"))), SelectionDecision.SELECT_IN_SCOPE, "LISTING_GEOGRAPHY_COMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Berlin", country="Germany"), JobLocation("Vienna", country="Austria"))), SelectionDecision.SKIP_EXPLICITLY_OUT_OF_SCOPE, "ALL_LISTING_LOCATIONS_EXPLICITLY_INCOMPATIBLE"),
        (ListingFacts(locations=(JobLocation("Berlin", country="Germany"), JobLocation("Brno"))), SelectionDecision.SELECT_IN_SCOPE, "LISTING_GEOGRAPHY_COMPATIBLE"),
    ],
)
def test_conservative_geography_selection(facts, decision, reason):
    first = select_for_detail(facts, SCOPE)
    second = select_for_detail(facts, SCOPE)
    assert first == second
    assert first.decision is decision
    assert first.reason == reason


def test_listing_fingerprint_is_normalized_deterministic_and_independent_of_metadata():
    instant = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    first = ListingFacts(
        title="  Data\u00a0Lead ",
        locations=(JobLocation("Prague,  Czechia"), JobLocation("Brno")),
        work_mode=WorkMode.HYBRID,
        source_updated_at=instant,
    )
    second = ListingFacts(
        title="Data Lead",
        locations=(JobLocation("Brno"), JobLocation("Prague, Czechia")),
        work_mode=WorkMode.HYBRID,
        source_updated_at=instant.astimezone(timezone(timedelta(hours=2))),
    )
    assert listing_facts_fingerprint(first) == listing_facts_fingerprint(second)
    a = JobReference("acme", "1", "https://example.test/1", {"secret": "a"}, first)
    b = JobReference("acme", "1", "https://example.test/1", {"secret": "b"}, first)
    assert listing_facts_fingerprint(a.listing_facts) == listing_facts_fingerprint(b.listing_facts)


def test_measurement_uses_zero_details_zero_state_and_omits_opaque_metadata(tmp_path, monkeypatch):
    companies = tmp_path / "companies.yaml"
    companies.write_text(
        """companies:
  - company_id: fixture
    company_name: Fixture
    adapter: generic_html
    endpoint_url: https://example.test/jobs
    options:
      selectors:
        job_container: .job
""",
        encoding="utf-8",
    )

    class Adapter:
        detail_calls = 0

        def list_jobs(self, config):
            return [JobReference(
                "fixture", "1", "https://example.test/1",
                {"api_key": "must-not-leak"},
                ListingFacts("Data Lead", (JobLocation("Prague"),)),
            )]

        def fetch_job(self, reference):
            self.detail_calls += 1
            raise AssertionError("measurement called fetch_job")

    adapter = Adapter()
    monkeypatch.setattr("opportunity_radar.scope_measurement.AdapterRegistry.create", lambda config: adapter)
    output = tmp_path / "measurement.json"
    artifact, path = run_scope_measurement(companies, "config/market_scope.yaml", output, "offline")
    assert path == output and output.exists()
    assert adapter.detail_calls == 0
    assert artifact["zero_detail_requests"] is True
    assert artifact["zero_semantic_calls"] is True
    assert artifact["zero_phase2_state_writes"] is True
    assert not list(tmp_path.glob("*.sqlite*"))
    assert artifact["global"]["selected_for_detail"] == 1
    assert artifact["global"]["projected_network_detail_requests"] == 1
    assert "must-not-leak" not in output.read_text(encoding="utf-8")
    assert json.loads(output.read_text())["references"][0]["selection_decision"] == "SELECT_IN_SCOPE"


def test_measurement_captures_bounded_source_diagnostics_without_details(tmp_path, monkeypatch):
    companies = tmp_path / "companies.yaml"
    companies.write_text(
        """companies:
  - company_id: sf
    company_name: SuccessFactors Fixture
    adapter: successfactors
    endpoint_url: https://example.test/search
    options:
      selectors:
        job_container: .job
""",
        encoding="utf-8",
    )

    class Adapter:
        detail_calls = 0

        def enable_source_diagnostics(self, pages):
            self.source_diagnostics = [{"page_index": 0, "response_url": "https://example.test/search"}]

        def list_jobs(self, config):
            return [JobReference("sf", "1", "https://example.test/1", listing_facts=ListingFacts("Role"))]

        def fetch_job(self, reference):
            self.detail_calls += 1
            raise AssertionError("measurement called fetch_job")

    adapter = Adapter()
    monkeypatch.setattr("opportunity_radar.scope_measurement.AdapterRegistry.create", lambda config: adapter)
    artifact, _ = run_scope_measurement(
        companies, "config/market_scope.yaml", tmp_path / "sf.json", "sf-diagnostic",
        successfactors_diagnostic_pages=1,
    )
    assert adapter.detail_calls == 0
    assert artifact["source_contract_diagnostics"][0]["pages"][0]["page_index"] == 0
    assert artifact["zero_phase2_state_writes"] is True
