from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from opportunity_radar.market_status import (
    CurrentCandidateMarketStatus,
    MarketReasonCode,
    evaluate_current_candidate_market,
    load_market_normalization_rules,
)
from opportunity_radar.models import JobLocation, JobReference, NormalizedJob, WorkMode
from opportunity_radar.phase3_benchmark import semantic_job_from_normalized
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import SemanticJobInput
from opportunity_radar.state_models import DetailObservation, SourceOutcome
from opportunity_radar.state_repository import SCHEMA_VERSION, StateRepository


ROOT = Path(__file__).parents[1]
RULES = load_market_normalization_rules(ROOT / "config/market_status_rules.yaml")
TAXONOMY = load_taxonomy(ROOT / "config/taxonomy.yaml")
PRIMARY = load_candidate_profile(ROOT / "config/candidate.yaml", TAXONOMY)
PORTABILITY = load_candidate_profile(ROOT / "config/candidate_portability_test.yaml", TAXONOMY)


def job(
    *,
    location: str = "Prague, Czechia",
    city: str | None = "Prague",
    country: str | None = "Czechia",
    work_mode: str = "onsite",
    description: str = "",
) -> SemanticJobInput:
    return SemanticJobInput(
        company_name="Fixture Company",
        title="Fixture role",
        description=description,
        locations=({"raw": location, "city": city, "region": None, "country": country},),
        work_mode=work_mode,
    )


def assess(value: SemanticJobInput, candidate=PRIMARY):
    return evaluate_current_candidate_market(value, candidate, RULES)


def codes(value) -> set[MarketReasonCode]:
    return {reason.code for reason in value.reasons}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (job(work_mode="onsite"), CurrentCandidateMarketStatus.IN_SCOPE),
        (job(work_mode="hybrid"), CurrentCandidateMarketStatus.IN_SCOPE),
        (job(location="Brno, Czechia", city="Brno", work_mode="hybrid"), CurrentCandidateMarketStatus.OUT_OF_SCOPE),
        (job(location="Chicago, United States", city="Chicago", country="United States", work_mode="onsite"), CurrentCandidateMarketStatus.OUT_OF_SCOPE),
        (job(location="Unparseable place", city=None, country=None, work_mode="onsite"), CurrentCandidateMarketStatus.UNCERTAIN),
        (job(location="Cork, IE +2 more…", city="Cork", country="Ireland", work_mode="onsite"), CurrentCandidateMarketStatus.UNCERTAIN),
    ],
)
def test_bounded_onsite_and_location_statuses(value, expected):
    assert assess(value).status is expected


def test_incomplete_multi_location_is_resolved_only_by_explicit_accepted_member():
    value = SemanticJobInput(
        "Fixture Company", "Role", "",
        (
            {"raw": "Prague, Czechia", "city": "Prague", "country": "Czechia"},
            {"raw": "2 Locations", "city": None, "country": None},
        ),
        "hybrid",
    )
    result = assess(value)
    assert result.status is CurrentCandidateMarketStatus.IN_SCOPE
    assert MarketReasonCode.INCOMPLETE_MULTI_LOCATION not in codes(result)


def test_confirmed_czech_remote_with_compatible_hours_is_in_scope():
    value = job(
        location="Remote - Czechia", city=None, country="Czechia", work_mode="remote",
        description="Employees may work remotely from Czechia during European working hours.",
    )
    result = assess(value)
    assert result.status is CurrentCandidateMarketStatus.IN_SCOPE
    assert {MarketReasonCode.REMOTE_RESIDENCE_CONFIRMED, MarketReasonCode.WORKING_HOURS_COMPATIBLE} <= codes(result)


def test_remote_restricted_to_foreign_country_is_out_of_scope():
    value = job(
        location="Remote - United States", city=None, country="United States", work_mode="remote",
        description="Remote role. Candidates must reside in the United States.",
    )
    result = assess(value)
    assert result.status is CurrentCandidateMarketStatus.OUT_OF_SCOPE
    assert MarketReasonCode.REMOTE_COUNTRY_RESTRICTED in codes(result)


def test_remote_access_and_missing_authorization_evidence_stay_uncertain():
    remote = assess(job(location="Belgium", city="Brussels", country="Belgium", work_mode="remote", description="Remote role."))
    europe = assess(job(location="Remote - Europe", city=None, country=None, work_mode="remote", description="Remote across Europe."))
    authorization = assess(job(location="Düsseldorf, Germany", city="Düsseldorf", country="Germany", work_mode="remote", description="Valid work authorization is required."))
    assert remote.status is CurrentCandidateMarketStatus.UNCERTAIN
    assert europe.status is CurrentCandidateMarketStatus.UNCERTAIN
    assert MarketReasonCode.REMOTE_ELIGIBILITY_UNKNOWN in codes(remote)
    assert authorization.status is CurrentCandidateMarketStatus.UNCERTAIN
    assert MarketReasonCode.WORK_AUTHORIZATION_UNKNOWN in codes(authorization)


def test_explicit_us_authorization_incompatibility_is_out_of_scope(tmp_path):
    raw = yaml.safe_load((ROOT / "config/candidate.yaml").read_text(encoding="utf-8"))
    raw["profile"]["version"] += 1
    raw["market_access_policy"]["work_access"]["United States"] = "INCOMPATIBLE"
    # Exercise an explicit assertion without changing the primary profile's
    # conservative foreign_default=UNKNOWN policy.
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    candidate = load_candidate_profile(path, TAXONOMY)
    value = job(
        location="New York, United States", city="New York", country="United States", work_mode="remote",
        description="Candidates must be authorized to be employed in the U.S. This position requires permanent work authorization in the United States.",
    )
    result = assess(value, candidate)
    assert result.status is CurrentCandidateMarketStatus.OUT_OF_SCOPE
    assert MarketReasonCode.WORK_AUTHORIZATION_INCOMPATIBLE in codes(result)


def test_required_language_none_and_comprehension_only_are_distinct():
    japanese = assess(job(description="Professional Japanese is required."))
    slovak = assess(job(description="Professional Slovak is required."))
    alternative = assess(job(description="Professional Japanese or English is required."))
    assert japanese.status is CurrentCandidateMarketStatus.OUT_OF_SCOPE
    assert MarketReasonCode.REQUIRED_LANGUAGE_INCOMPATIBLE in codes(japanese)
    assert slovak.status is CurrentCandidateMarketStatus.IN_SCOPE
    assert MarketReasonCode.REQUIRED_LANGUAGE_SUPPORTED in codes(slovak)
    assert alternative.status is CurrentCandidateMarketStatus.IN_SCOPE


def test_relocation_posture_does_not_promote_foreign_onsite():
    result = assess(job(location="Düsseldorf, Germany", city="Düsseldorf", country="Germany", work_mode="onsite"))
    assert result.status is CurrentCandidateMarketStatus.OUT_OF_SCOPE
    foreign_reason = next(reason for reason in result.reasons if reason.code is MarketReasonCode.FOREIGN_ONSITE_INCOMPATIBLE)
    assert "relocation.normal_shortlist=False" in foreign_reason.candidate_policy_evidence


def test_fingerprints_are_deterministic_and_auditable():
    first = assess(job())
    second = assess(job())
    changed = assess(job(description="Additional material market evidence."))
    assert first == second
    assert first.input_fingerprint == second.input_fingerprint
    assert first.assessment_fingerprint == second.assessment_fingerprint
    assert changed.input_fingerprint != first.input_fingerprint
    assert first.payload()["status"] == "IN_SCOPE"
    json.dumps(first.payload())
    assert first.evidence


def test_fingerprint_includes_only_supported_market_supplemental_evidence():
    base = job()
    opaque = SemanticJobInput(**{
        **base.__dict__, "supplemental_evidence": {"opaque_adapter_metadata": "ignored"},
    })
    relevant = SemanticJobInput(**{
        **base.__dict__, "supplemental_evidence": {"required_languages": "Japanese required"},
    })
    assert assess(base).input_fingerprint == assess(opaque).input_fingerprint
    assert assess(base).input_fingerprint != assess(relevant).input_fingerprint


def test_same_evaluator_is_portable_and_candidate_policy_drives_difference():
    value = job(location="Chicago, United States", city="Chicago", country="United States", work_mode="onsite")
    assert assess(value, PRIMARY).status is CurrentCandidateMarketStatus.OUT_OF_SCOPE
    assert assess(value, PORTABILITY).status is CurrentCandidateMarketStatus.UNCERTAIN


def test_policy_only_change_changes_market_result_without_semantic_identity_or_calls(tmp_path, monkeypatch):
    raw = yaml.safe_load((ROOT / "config/candidate.yaml").read_text(encoding="utf-8"))
    raw["profile"]["version"] += 1
    raw["market_access_policy"]["onsite_hybrid"]["outside_accepted_locations"] = "UNCERTAIN"
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    changed = load_candidate_profile(path, TAXONOMY)
    monkeypatch.setattr(
        "opportunity_radar.semantic.DeterministicSemanticAssessor.assess",
        lambda *args, **kwargs: pytest.fail("market evaluator must not call semantic assessor"),
    )
    value = job(location="Chicago, United States", city="Chicago", country="United States", work_mode="onsite")
    assert assess(value, PRIMARY).status is CurrentCandidateMarketStatus.OUT_OF_SCOPE
    assert assess(value, changed).status is CurrentCandidateMarketStatus.UNCERTAIN
    assert changed.market_access_policy_fingerprint != PRIMARY.market_access_policy_fingerprint
    assert changed.semantic_profile_fingerprint == PRIMARY.semantic_profile_fingerprint
    assert changed.scoring_preference_fingerprint == PRIMARY.scoring_preference_fingerprint


def test_evaluation_does_not_mutate_active_phase2_state_or_schema(tmp_path):
    repository = StateRepository(tmp_path / "state.sqlite3")
    observed = NormalizedJob(
        "acme", "Acme", "US-1", "US role",
        [JobLocation("Chicago, United States", "Chicago", "Illinois", "United States")],
        WorkMode.ONSITE, "https://example.test/jobs/US-1", "On-site in Chicago.",
        None, None, None, None, "fixture", datetime(2026, 9, 5, tzinfo=timezone.utc),
    )
    reference = JobReference("acme", "US-1", observed.canonical_url)
    outcome = SourceOutcome(
        "acme", "Acme", "fixture", "SUCCESS", observed.retrieved_at,
        [reference], [DetailObservation(reference, observed)], True, True, 1,
    )
    repository.create_run("run-1", "2026-09-05T00:00:00+00:00")
    repository.apply_outcome("run-1", outcome)
    before = {table: [dict(row) for row in repository.rows(table)] for table in ("job_instances", "job_observations", "events")}
    result = assess(semantic_job_from_normalized(observed))
    after = {table: [dict(row) for row in repository.rows(table)] for table in before}
    assert result.status is CurrentCandidateMarketStatus.OUT_OF_SCOPE
    assert before == after
    assert after["job_instances"][0]["lifecycle_state"] == "ACTIVE"
    with repository.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 3


def test_live_validation_v1_regression_directions():
    raw = json.loads((ROOT / "tests/fixtures/phase4/market_status_cases.json").read_text(encoding="utf-8"))
    assert raw["fixture_version"] == 1
    results = {}
    for case in raw["cases"]:
        item = case["job"]
        semantic_job = SemanticJobInput(
            item["company_name"], item.get("title"), item.get("description", ""),
            tuple(item.get("locations", [])), item["work_mode"],
            item.get("employment_type"), item.get("department"),
        )
        results[case["case_id"]] = assess(semantic_job).status.value
        assert results[case["case_id"]] == case["expected"]
    assert len(results) == 10


def test_country_code_is_positional_not_arbitrary_substring():
    # Regression: Dutch postal suffix CZ must never be interpreted as Czechia.
    value = job(location="2596 CZ, Den Haag", city=None, country=None, work_mode="onsite")
    result = assess(value)
    assert result.status is CurrentCandidateMarketStatus.UNCERTAIN
    assert MarketReasonCode.ACCEPTED_LOCATION_COMPATIBLE not in codes(result)


def test_explicit_texas_location_is_out_of_scope_without_inventing_work_mode():
    result = assess(job(
        location="El Paso, Texas", city=None, country=None,
        work_mode="unspecified",
    ))
    assert result.status is CurrentCandidateMarketStatus.OUT_OF_SCOPE
    assert MarketReasonCode.WORK_MODE_UNKNOWN in codes(result)
    assert MarketReasonCode.EXPLICIT_FOREIGN_REGION_INCOMPATIBLE in codes(result)
    assert any(
        item.normalized_value == "United States"
        for item in result.evidence
        if item.kind == "location"
    )


def test_california_regression_remains_out_of_scope_with_unknown_work_mode():
    result = assess(job(
        location="Santa Clara, California", city=None, country=None,
        work_mode="unspecified",
    ))
    assert result.status is CurrentCandidateMarketStatus.OUT_OF_SCOPE


@pytest.mark.parametrize("location", ["Textanalysis", "Contextual", "Californication"])
def test_state_like_substrings_do_not_become_us_geography(location):
    result = assess(job(
        location=location, city=None, country=None, work_mode="unspecified",
    ))
    assert result.status is CurrentCandidateMarketStatus.UNCERTAIN
    assert MarketReasonCode.EXPLICIT_FOREIGN_REGION_INCOMPATIBLE not in codes(result)


def test_ambiguous_region_name_stays_uncertain_without_country_context():
    result = assess(job(
        location="Georgia", city=None, country=None, work_mode="unspecified",
    ))
    assert result.status is CurrentCandidateMarketStatus.UNCERTAIN


def test_unknown_work_mode_does_not_change_prague_or_remote_semantics():
    prague = assess(job(work_mode="unspecified"))
    remote = assess(job(
        location="Belgium", city="Brussels", country="Belgium",
        work_mode="remote", description="Remote role.",
    ))
    assert prague.status is CurrentCandidateMarketStatus.UNCERTAIN
    assert remote.status is CurrentCandidateMarketStatus.UNCERTAIN
    assert MarketReasonCode.EXPLICIT_FOREIGN_REGION_INCOMPATIBLE not in codes(remote)
