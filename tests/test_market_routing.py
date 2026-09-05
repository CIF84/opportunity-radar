from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from opportunity_radar.live_validation import (
    _assessed_pool,
    _clustered_assessed_pool,
    build_preflight,
)
from opportunity_radar.market_routing import (
    MarketRoutingReason,
    assess_routed_opportunity,
    compose_market_routing,
)
from opportunity_radar.market_status import (
    CurrentCandidateMarketStatus,
    load_market_normalization_rules,
)
from opportunity_radar.models import JobLocation, JobReference, NormalizedJob, WorkMode
from opportunity_radar.phase3_benchmark import semantic_job_from_normalized
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import (
    CORE_DIMENSIONS,
    DimensionScore,
    EligibilityStatus,
    Recommendation,
    SemanticAssessment,
    SemanticJobInput,
)
from opportunity_radar.phase3_pipeline import assess_opportunity
from opportunity_radar.phase3_repository import Phase3Repository
from opportunity_radar.semantic import SEMANTIC_CONTRACT_VERSION
from opportunity_radar.state_models import DetailObservation, SourceOutcome
from opportunity_radar.state_repository import SCHEMA_VERSION, StateRepository


ROOT = Path(__file__).parents[1]
TAXONOMY = load_taxonomy(ROOT / "config/taxonomy.yaml")
PROFILE = load_candidate_profile(ROOT / "config/candidate.yaml", TAXONOMY)
RULES = load_market_normalization_rules(ROOT / "config/market_status_rules.yaml")
AT = datetime(2026, 9, 5, tzinfo=timezone.utc)


class HighAssessor:
    assessor_id = "external-structured"
    assessor_version = "1:gpt-5.6-luna"

    def __init__(self):
        self.calls = 0

    def assess(self, job, candidate, features):
        self.calls += 1
        dimensions = {
            name: DimensionScore(5, "HIGH", "Deterministic test evidence")
            for name in CORE_DIMENSIONS
        }
        return SemanticAssessment(
            dimensions, (), (), (), self.assessor_id, self.assessor_version,
            SEMANTIC_CONTRACT_VERSION,
        )


def semantic_job(
    location: str,
    city: str | None,
    country: str | None,
    mode: str,
    description: str = "Lead product analytics and AI strategy.",
) -> SemanticJobInput:
    return SemanticJobInput(
        "Acme", "Senior strategy role", description,
        ({"raw": location, "city": city, "region": None, "country": country},),
        mode,
    )


def normalized_job(external_id: str, *, foreign: bool) -> NormalizedJob:
    location = (
        JobLocation("Chicago, United States", "Chicago", "Illinois", "United States")
        if foreign else JobLocation("Prague, Czechia", "Prague", None, "Czechia")
    )
    return NormalizedJob(
        "acme", "Acme", external_id, f"Senior role {external_id}", [location],
        WorkMode.HYBRID, f"https://example.test/{external_id}",
        "Lead product analytics and AI strategy with senior stakeholders.",
        None, None, "Full time", "Product", "fixture", AT,
    )


def variant_job(
    external_id: str,
    location: JobLocation,
    *,
    title: str = "Senior Business Analyst - Inventory",
    description_tail: str,
) -> NormalizedJob:
    core = (
        "The inventory analytics team owns pricing and supply decisions. "
        "You will identify opportunities, define metrics, design experiments, "
        "partner with product and engineering, communicate recommendations to "
        "senior stakeholders, and lead implementation through measurable results. "
        "Requirements include advanced analytics, commercial judgment, SQL, and "
        "cross-functional delivery in a complex marketplace. "
    )
    return NormalizedJob(
        "acme", "Acme", external_id, title, [location], WorkMode.HYBRID,
        f"https://example.test/jobs/{external_id}",
        core + "We offer you " + description_tail,
        None, None, "Full time", "Analytics", "fixture", AT,
    )


def seed_state(tmp_path, *jobs: NormalizedJob) -> tuple[StateRepository, list[tuple[int, int, str, SemanticJobInput]]]:
    state = StateRepository(tmp_path / "state.sqlite3")
    references = [JobReference(job.company_id, job.external_job_id, job.canonical_url) for job in jobs]
    state.create_run("run-1", AT.isoformat())
    state.apply_outcome("run-1", SourceOutcome(
        "acme", "Acme", "fixture", "SUCCESS", AT, references,
        [DetailObservation(reference, job) for reference, job in zip(references, jobs)],
        True, True, len(references),
    ))
    state.finish_run("run-1", AT.isoformat(), "COMPLETED")
    rows = []
    with state.connect() as connection:
        for row in connection.execute(
            """SELECT ji.job_instance_id,ji.latest_observation_id,jo.fingerprint,
                      jo.normalized_snapshot
               FROM job_instances ji JOIN job_observations jo
                 ON jo.job_observation_id=ji.latest_observation_id
               ORDER BY ji.job_instance_id"""
        ):
            raw = json.loads(row["normalized_snapshot"])
            rows.append((
                row["job_instance_id"], row["latest_observation_id"], row["fingerprint"],
                SemanticJobInput(
                    raw["company_name"], raw["title"], raw["description"],
                    tuple(raw["locations"]), raw["work_mode"],
                    raw.get("employment_type"), raw.get("department"),
                ),
            ))
    return state, rows


@pytest.mark.parametrize(
    ("recommendation", "expected", "capped"),
    [
        (Recommendation.APPLY, Recommendation.REVIEW, True),
        (Recommendation.REVIEW, Recommendation.REVIEW, False),
        (Recommendation.LOW_PRIORITY, Recommendation.LOW_PRIORITY, False),
        (Recommendation.INELIGIBLE, Recommendation.INELIGIBLE, False),
    ],
)
def test_uncertain_recommendation_cap_never_promotes(recommendation, expected, capped):
    decision = compose_market_routing(
        CurrentCandidateMarketStatus.UNCERTAIN,
        EligibilityStatus.ELIGIBLE,
        recommendation,
    )
    assert decision.include_in_normal_shortlist is True
    assert decision.eligible_for_semantic_processing is True
    assert decision.recommendation is expected
    assert decision.cap_applied is capped
    assert decision.recommendation_cap is Recommendation.REVIEW


def test_new_out_of_scope_cache_miss_stops_before_semantics():
    assessor = HighAssessor()
    result = assess_routed_opportunity(
        semantic_job("Chicago, United States", "Chicago", "United States", "hybrid"),
        PROFILE, TAXONOMY, assessor, RULES,
    )
    assert result.market.status is CurrentCandidateMarketStatus.OUT_OF_SCOPE
    assert result.routing.reason is MarketRoutingReason.OUT_OF_SCOPE_EXCLUDED
    assert result.routing.include_in_normal_shortlist is False
    assert result.opportunity is None
    assert assessor.calls == 0


def test_uncertain_would_be_apply_is_capped_but_in_scope_is_unchanged():
    assessor = HighAssessor()
    uncertain = assess_routed_opportunity(
        semantic_job("Unknown", None, None, "remote", "Remote role."),
        PROFILE, TAXONOMY, assessor, RULES,
    )
    in_scope = assess_routed_opportunity(
        semantic_job("Prague, Czechia", "Prague", "Czechia", "hybrid"),
        PROFILE, TAXONOMY, assessor, RULES,
    )
    assert uncertain.opportunity.recommendation is Recommendation.REVIEW
    assert uncertain.routing.recommendation_before_market_policy is Recommendation.APPLY
    assert uncertain.routing.cap_applied is True
    assert in_scope.opportunity.recommendation is Recommendation.APPLY
    assert in_scope.routing.cap_applied is False
    assert assessor.calls == 2


def test_in_scope_phase3_result_is_equivalent_to_existing_pipeline():
    value = semantic_job("Prague, Czechia", "Prague", "Czechia", "hybrid")
    direct = assess_opportunity(value, PROFILE, TAXONOMY, HighAssessor())
    routed = assess_routed_opportunity(
        value, PROFILE, TAXONOMY, HighAssessor(), RULES,
    )
    assert routed.market.status is CurrentCandidateMarketStatus.IN_SCOPE
    assert routed.opportunity == direct
    assert routed.routing.reason is MarketRoutingReason.NORMAL_MARKET_FLOW


def test_hard_ineligible_remains_restrictive_without_semantic_call(tmp_path):
    raw = yaml.safe_load((ROOT / "config/candidate.yaml").read_text(encoding="utf-8"))
    raw["profile"]["version"] += 1
    raw["hard_constraints"]["relocation"]["prohibited"] = True
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    candidate = load_candidate_profile(path, TAXONOMY)
    assessor = HighAssessor()
    result = assess_routed_opportunity(
        semantic_job(
            "Prague, Czechia", "Prague", "Czechia", "hybrid",
            "The successful candidate must relocate.",
        ),
        candidate, TAXONOMY, assessor, RULES,
    )
    assert result.market.status is CurrentCandidateMarketStatus.IN_SCOPE
    assert result.opportunity.recommendation is Recommendation.INELIGIBLE
    assert result.routing.include_in_normal_shortlist is False
    assert result.routing.reason is MarketRoutingReason.HARD_INELIGIBLE_EXCLUDED
    assert assessor.calls == 0


def test_existing_out_of_scope_semantics_remain_but_ranked_pool_excludes_job(tmp_path):
    state, rows = seed_state(
        tmp_path, normalized_job("in", foreign=False), normalized_job("out", foreign=True),
    )
    repository = Phase3Repository(state)
    assessor = HighAssessor()
    for job_id, observation_id, fingerprint, job in rows:
        assess_opportunity(
            job, PROFILE, TAXONOMY, assessor, repository=repository,
            job_instance_id=job_id, job_observation_id=observation_id,
            content_fingerprint=fingerprint,
        )
    before_semantics = [dict(row) for row in state.rows("semantic_assessments")]
    before_events = [dict(row) for row in state.rows("events")]

    pool = _assessed_pool(state.path, PROFILE, assessor.assessor_version, RULES)

    assert [item["title"] for item in pool] == ["Senior role in"]
    assert pool[0]["market_status"] == "IN_SCOPE"
    assert [dict(row) for row in state.rows("semantic_assessments")] == before_semantics
    assert [dict(row) for row in state.rows("events")] == before_events
    assert {row["lifecycle_state"] for row in state.rows("job_instances")} == {"ACTIVE"}
    assert SCHEMA_VERSION == 3


def test_preflight_counts_after_routing_and_out_of_scope_cache_does_not_add_cost(tmp_path):
    state, rows = seed_state(
        tmp_path, normalized_job("in", foreign=False), normalized_job("out", foreign=True),
    )
    assessor = HighAssessor()
    for job_id, observation_id, fingerprint, job in rows:
        assess_opportunity(
            job, PROFILE, TAXONOMY, assessor, repository=Phase3Repository(state),
            job_instance_id=job_id, job_observation_id=observation_id,
            content_fingerprint=fingerprint,
        )
    result = build_preflight(state.path)
    assert result["market_status"] == {
        "IN_SCOPE": 1, "UNCERTAIN": 0, "OUT_OF_SCOPE": 1,
    }
    assert result["jobs_eligible_for_semantic_processing"] == 1
    assert result["compatible_luna_cache_hits"] == 1
    assert result["out_of_scope_existing_cache_hits"] == 1
    assert result["luna_cache_misses"] == 0
    assert result["expected_external_calls"] == 0


def test_policy_only_reroute_reuses_semantics_and_preserves_content_fingerprint(tmp_path):
    state, rows = seed_state(tmp_path, normalized_job("policy", foreign=True))
    job_id, observation_id, fingerprint, job = rows[0]
    repository = Phase3Repository(state)
    initial_assessor = HighAssessor()
    assess_opportunity(
        job, PROFILE, TAXONOMY, initial_assessor, repository=repository,
        job_instance_id=job_id, job_observation_id=observation_id,
        content_fingerprint=fingerprint,
    )
    assert initial_assessor.calls == 1

    raw = yaml.safe_load((ROOT / "config/candidate.yaml").read_text(encoding="utf-8"))
    raw["profile"]["version"] += 1
    raw["market_access_policy"]["onsite_hybrid"]["outside_accepted_locations"] = "UNCERTAIN"
    candidate_path = tmp_path / "candidate-reroute.yaml"
    candidate_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    rerouted_candidate = load_candidate_profile(candidate_path, TAXONOMY)
    no_call_assessor = HighAssessor()
    rerouted = assess_routed_opportunity(
        job, rerouted_candidate, TAXONOMY, no_call_assessor, RULES,
        repository=repository, job_instance_id=job_id,
        job_observation_id=observation_id, content_fingerprint=fingerprint,
    )

    assert rerouted.market.status is CurrentCandidateMarketStatus.UNCERTAIN
    assert rerouted.opportunity.semantic_reused is True
    assert rerouted.opportunity.recommendation is Recommendation.REVIEW
    assert no_call_assessor.calls == 0
    assert len(state.rows("semantic_assessments")) == 1
    assert state.rows("job_instances")[0]["current_fingerprint"] == fingerprint
    assert rerouted_candidate.semantic_profile_fingerprint == PROFILE.semantic_profile_fingerprint
    assert rerouted_candidate.scoring_preference_fingerprint == PROFILE.scoring_preference_fingerprint


def test_clustered_pool_reuses_prior_opportunity_across_market_only_profile_change(tmp_path):
    state, rows = seed_state(tmp_path, normalized_job("market-only", foreign=False))
    raw = yaml.safe_load((ROOT / "config/candidate.yaml").read_text(encoding="utf-8"))
    raw["profile"]["version"] += 1
    raw["market_access_policy"]["onsite_hybrid"]["outside_accepted_locations"] = "UNCERTAIN"
    changed_path = tmp_path / "market-only-profile.yaml"
    changed_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    changed = load_candidate_profile(changed_path, TAXONOMY)
    job_id, observation_id, fingerprint, job = rows[0]
    assessor = HighAssessor()
    assess_opportunity(
        job, changed, TAXONOMY, assessor, repository=Phase3Repository(state),
        job_instance_id=job_id, job_observation_id=observation_id,
        content_fingerprint=fingerprint,
    )
    before = [dict(row) for row in state.rows("semantic_assessments")]

    pool, _ = _clustered_assessed_pool(
        state.path, PROFILE, assessor.assessor_version, RULES,
    )

    assert len(pool) == 1
    assert pool[0]["job_instance_id"] == job_id
    assert [dict(row) for row in state.rows("semantic_assessments")] == before
    assert changed.semantic_profile_fingerprint == PROFILE.semantic_profile_fingerprint
    assert changed.scoring_preference_fingerprint == PROFILE.scoring_preference_fingerprint
    assert changed.full_profile_fingerprint != PROFILE.full_profile_fingerprint


def test_live_validation_regression_routing_uses_frozen_slice2_evidence():
    raw = json.loads(
        (ROOT / "tests/fixtures/phase4/market_status_cases.json").read_text(encoding="utf-8")
    )
    included = {}
    for case in raw["cases"]:
        item = case["job"]
        job = SemanticJobInput(
            item["company_name"], item.get("title"), item.get("description", ""),
            tuple(item.get("locations", [])), item["work_mode"],
            item.get("employment_type"), item.get("department"),
        )
        routed = assess_routed_opportunity(job, PROFILE, TAXONOMY, HighAssessor(), RULES)
        included[case["case_id"]] = routed.routing
    explicit_foreign = {
        "johnson_johnson_us_only", "pfizer_us_authorization",
        "pure_storage_santa_clara", "wpp_chicago", "wpp_new_york",
        "red_hat_tokyo_japanese", "wpp_mexico_city", "wpp_dusseldorf",
    }
    for case_id in explicit_foreign:
        assert included[case_id].include_in_normal_shortlist is False
        assert included[case_id].eligible_for_semantic_processing is False
    for case_id in {"deutsche_boerse_cork_incomplete", "klaxoon_remote_unresolved"}:
        assert included[case_id].include_in_normal_shortlist is True
        assert included[case_id].recommendation is Recommendation.REVIEW
        assert included[case_id].cap_applied is True


def test_clustered_pool_collapses_variants_and_reuses_member_semantics(tmp_path):
    jobs = (
        variant_job("bratislava", JobLocation("Bratislava, Slovakia", "Bratislava", None, "Slovakia"), description_tail="a Bratislava office and local benefits."),
        variant_job("brno", JobLocation("Brno, Czechia", "Brno", None, "Czechia"), description_tail="a Brno office and local benefits."),
        variant_job("barcelona", JobLocation("Barcelona, Spain", "Barcelona", None, "Spain"), description_tail="a Barcelona office and local benefits."),
        variant_job("prague", JobLocation("Prague, Czechia", "Prague", None, "Czechia"), description_tail="a Prague office and local benefits."),
    )
    state, rows = seed_state(tmp_path, *jobs)
    assessor = HighAssessor()
    repository = Phase3Repository(state)
    for job_id, observation_id, fingerprint, job in rows:
        assess_opportunity(
            job, PROFILE, TAXONOMY, assessor, repository=repository,
            job_instance_id=job_id, job_observation_id=observation_id,
            content_fingerprint=fingerprint,
        )
    before_semantics = [dict(row) for row in state.rows("semantic_assessments")]
    before_events = [dict(row) for row in state.rows("events")]

    pool, diagnostics = _clustered_assessed_pool(
        state.path, PROFILE, assessor.assessor_version, RULES,
    )

    assert len(pool) == 1
    assert pool[0]["member_count"] == 4
    assert pool[0]["title"] == "Senior Business Analyst - Inventory"
    assert pool[0]["locations"][0]["city"] == "Prague"
    assert pool[0]["preferred_variant"]["preferred_variant_job_instance_id"] == pool[0]["job_instance_id"]
    assert len(diagnostics) == 1
    assert diagnostics[0]["included_in_normal_shortlist"] is True
    assert [dict(row) for row in state.rows("semantic_assessments")] == before_semantics
    assert [dict(row) for row in state.rows("events")] == before_events
    assert {row["lifecycle_state"] for row in state.rows("job_instances")} == {"ACTIVE"}
    assert SCHEMA_VERSION == 3


def test_all_out_of_scope_cluster_is_diagnostic_only(tmp_path):
    core_tail = "local compensation and office benefits."
    jobs = (
        variant_job("new-york", JobLocation("New York, United States", "New York", None, "United States"), title="Consultant - Growth Consulting, WPP Open", description_tail=core_tail),
        variant_job("chicago", JobLocation("Chicago, United States", "Chicago", None, "United States"), title="Consultant - Growth Consulting, WPP Open", description_tail=core_tail),
    )
    state, _ = seed_state(tmp_path, *jobs)
    assessor = HighAssessor()

    pool, diagnostics = _clustered_assessed_pool(
        state.path, PROFILE, assessor.assessor_version, RULES,
    )

    assert pool == []
    assert len(diagnostics) == 1
    assert diagnostics[0]["member_job_instance_ids"] == (1, 2)
    assert diagnostics[0]["included_in_normal_shortlist"] is False
    assert all(
        member["semantic_assessment_available"] is False
        for member in diagnostics[0]["members"]
    )
    assert assessor.calls == 0


def test_unassessed_preferred_member_is_not_replaced_or_assessed_implicitly(tmp_path):
    jobs = (
        variant_job("remote", JobLocation("Remote", None, None, None), description_tail="a remote arrangement."),
        variant_job("prague", JobLocation("Prague, Czechia", "Prague", None, "Czechia"), description_tail="a Prague office."),
    )
    state, rows = seed_state(tmp_path, *jobs)
    assessor = HighAssessor()
    remote = rows[0]
    assess_opportunity(
        remote[3], PROFILE, TAXONOMY, assessor, repository=Phase3Repository(state),
        job_instance_id=remote[0], job_observation_id=remote[1],
        content_fingerprint=remote[2],
    )
    calls_before_pool = assessor.calls

    pool, diagnostics = _clustered_assessed_pool(
        state.path, PROFILE, assessor.assessor_version, RULES,
    )

    assert pool == []
    assert diagnostics[0]["preferred_variant"]["preferred_variant_job_instance_id"] == 2
    assert diagnostics[0]["candidate_route_in_normal_shortlist"] is True
    assert diagnostics[0]["included_in_normal_shortlist"] is False
    assert assessor.calls == calls_before_pool


def test_member_closure_stays_independent_and_active_sibling_remains_actionable(tmp_path):
    jobs = (
        variant_job("brno", JobLocation("Brno, Czechia", "Brno", None, "Czechia"), description_tail="a Brno office."),
        variant_job("prague", JobLocation("Prague, Czechia", "Prague", None, "Czechia"), description_tail="a Prague office."),
    )
    state, rows = seed_state(tmp_path, *jobs)
    assessor = HighAssessor()
    for job_id, observation_id, fingerprint, job in rows:
        assess_opportunity(
            job, PROFILE, TAXONOMY, assessor, repository=Phase3Repository(state),
            job_instance_id=job_id, job_observation_id=observation_id,
            content_fingerprint=fingerprint,
        )
    prague_reference = JobReference(
        jobs[1].company_id, jobs[1].external_job_id, jobs[1].canonical_url,
    )
    state.create_run("run-2", AT.isoformat())
    state.apply_outcome("run-2", SourceOutcome(
        "acme", "Acme", "fixture", "SUCCESS", AT, [prague_reference], [],
        True, False, 1,
    ))
    state.finish_run("run-2", AT.isoformat(), "COMPLETED")
    events_before = [dict(row) for row in state.rows("events")]

    pool, diagnostics = _clustered_assessed_pool(
        state.path, PROFILE, assessor.assessor_version, RULES,
    )

    lifecycles = {
        row["external_job_id"]: row["lifecycle_state"]
        for row in state.rows("job_instances")
    }
    assert lifecycles == {"brno": "CLOSED", "prague": "ACTIVE"}
    assert len(pool) == 1
    assert pool[0]["member_job_instance_ids"] == [2]
    assert diagnostics[0]["clustering_method"] == "SINGLETON"
    assert [dict(row) for row in state.rows("events")] == events_before
