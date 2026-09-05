from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from opportunity_radar.market_status import (
    CurrentCandidateMarketStatus,
    evaluate_current_candidate_market,
    load_market_normalization_rules,
)
from opportunity_radar.opportunity_clustering import (
    CLUSTERING_METHOD_VERSION,
    ClusterMemberEvidence,
    cluster_opportunities,
    core_description_signature,
    select_preferred_variant,
)
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import EligibilityStatus, SemanticJobInput


ROOT = Path(__file__).parents[1]
TAXONOMY = load_taxonomy(ROOT / "config/taxonomy.yaml")
PROFILE = load_candidate_profile(ROOT / "config/candidate.yaml", TAXONOMY)
RULES = load_market_normalization_rules(ROOT / "config/market_status_rules.yaml")
CORE = (
    "The inventory analytics team owns pricing and supply decisions. "
    "You will identify opportunities, define metrics, design experiments, "
    "partner with product and engineering, communicate recommendations to "
    "senior stakeholders, and lead implementation through measurable results. "
    "Requirements include advanced analytics, commercial judgment, SQL, and "
    "cross-functional delivery in a complex marketplace. "
)


def member(
    job_id: int,
    *,
    company: str = "kiwi_com",
    title: str = "Senior Business Analyst - Inventory",
    description: str = CORE,
    location: str = "Prague, Czechia",
    city: str | None = "Prague",
    country: str | None = "Czechia",
    mode: str = "hybrid",
    lifecycle: str = "ACTIVE",
) -> ClusterMemberEvidence:
    return ClusterMemberEvidence(
        job_id, company, title, description,
        f"https://example.test/{company}/jobs/{job_id}", f"content-{job_id}",
        ({"raw": location, "city": city, "region": None, "country": country},),
        mode, "Full time", "Analytics", lifecycle, True,
        f"2026-09-{min(job_id, 28):02d}T00:00:00+00:00",
    )


def market(value: ClusterMemberEvidence):
    return evaluate_current_candidate_market(
        SemanticJobInput(
            "Fixture Employer", value.title, value.description or "",
            value.locations, value.work_mode, value.employment_type, value.department,
        ),
        PROFILE,
        RULES,
    )


def clustered(*members: ClusterMemberEvidence):
    result = cluster_opportunities(members)
    return next(item for item in result if len(item.member_job_instance_ids) > 1)


def test_known_kiwi_variants_cluster_with_exact_core_evidence():
    values = (
        member(1, description=CORE + "We offer you a Bratislava office and local benefits.", location="Bratislava, Slovakia", city="Bratislava", country="Slovakia"),
        member(2, description=CORE + "We offer you a Brno office and local benefits.", location="Brno, Czechia", city="Brno"),
        member(3, description=CORE + "We offer you a Barcelona office and local benefits.", location="Barcelona, Spain", city="Barcelona", country="Spain"),
        member(4, description=CORE + "We offer you a Prague office and local benefits.", location="Prague, Czechia"),
    )
    result = clustered(*values)
    assert result.member_job_instance_ids == (1, 2, 3, 4)
    assert result.clustering_method == "EXACT_TITLE_AND_CORE_DESCRIPTION"
    assert {item.signal for item in result.clustering_evidence} == {
        "EXACT_NORMALIZED_TITLE", "EXACT_CORE_DESCRIPTION_SIGNATURE",
        "DECLARED_VARIANT_FIELD_DIFFERENCE",
    }
    assert len({core_description_signature(item.description) for item in values}) == 1


def test_known_wpp_compensation_variants_cluster_without_fuzzy_matching():
    description = CORE + " The salary range is {salary}. We work together in person."
    values = (
        member(11, company="wpp", title="Consultant - Growth Consulting, WPP Open", description=description.format(salary="$75,000 — $180,000 USD"), location="New York, United States", city="New York", country="United States"),
        member(12, company="wpp", title="Consultant - Growth Consulting, WPP Open", description=description.format(salary="$125,365 — $170,204 USD"), location="Chicago, United States", city="Chicago", country="United States"),
    )
    result = clustered(*values)
    assert result.company_id == "wpp"
    assert result.member_job_instance_ids == (11, 12)
    assert len({core_description_signature(item.description) for item in values}) == 1


def test_false_merge_controls_and_singletons():
    first = member(1)
    different_duties = member(
        2,
        description=(
            "This role operates laboratory instruments and manages clinical "
            "quality controls. It owns sample preparation, biosafety reviews, "
            "regulated documentation, equipment calibration, and scientific "
            "protocol compliance across hospital research facilities. " * 2
        ),
    )
    other_employer = replace(first, job_instance_id=3, company_id="other", canonical_url="https://example.test/other/3")
    results = cluster_opportunities((first, different_duties, other_employer))
    assert len(results) == 3
    assert all(item.clustering_method == "SINGLETON" for item in results)


def test_identical_same_location_postings_are_not_assumed_to_be_variants():
    results = cluster_opportunities((member(1), member(2)))
    assert len(results) == 2
    assert all(item.member_job_instance_ids in {(1,), (2,)} for item in results)


def test_input_order_does_not_change_cluster_identity_or_fingerprint():
    values = (
        member(1),
        member(2, location="Brno, Czechia", city="Brno"),
        member(3, location="Barcelona, Spain", city="Barcelona", country="Spain"),
    )
    forward = cluster_opportunities(values)
    reverse = cluster_opportunities(reversed(values))
    assert forward == reverse
    assert forward[0].clustering_method_version == CLUSTERING_METHOD_VERSION


def test_membership_change_changes_cluster_fingerprint_without_changing_members():
    values = (
        member(1),
        member(2, location="Brno, Czechia", city="Brno"),
        member(3, location="Barcelona, Spain", city="Barcelona", country="Spain"),
    )
    two = clustered(*values[:2])
    three = clustered(*values)
    assert two.cluster_fingerprint != three.cluster_fingerprint
    assert values[0].content_fingerprint == "content-1"


def test_preferred_variant_uses_market_status_then_stable_ties():
    prague = member(4)
    uncertain = member(3, location="Remote", city=None, country=None, mode="remote")
    foreign = member(2, location="Barcelona, Spain", city="Barcelona", country="Spain")
    values = (foreign, uncertain, prague)
    cluster = clustered(*values)
    markets = {item.job_instance_id: market(item) for item in values}
    selection = select_preferred_variant(
        cluster,
        {item.job_instance_id: item for item in values},
        markets,
        {item.job_instance_id: EligibilityStatus.ELIGIBLE for item in values},
        PROFILE,
    )
    assert selection.preferred_variant_job_instance_id == 4
    assert selection.ordered_member_job_instance_ids == (4, 3, 2)
    assert markets[4].status is CurrentCandidateMarketStatus.IN_SCOPE
    assert markets[3].status is CurrentCandidateMarketStatus.UNCERTAIN
    assert markets[2].status is CurrentCandidateMarketStatus.OUT_OF_SCOPE


def test_closed_or_hard_ineligible_member_cannot_be_preferred():
    closed = member(1, lifecycle="CLOSED")
    active = member(2, location="Brno, Czechia", city="Brno")
    cluster = clustered(closed, active)
    markets = {item.job_instance_id: market(item) for item in (closed, active)}
    selection = select_preferred_variant(
        cluster, {1: closed, 2: active}, markets,
        {1: EligibilityStatus.ELIGIBLE, 2: EligibilityStatus.ELIGIBLE}, PROFILE,
    )
    assert selection.preferred_variant_job_instance_id == 2
    assert selection.ordered_member_job_instance_ids == (2,)

    none = select_preferred_variant(
        cluster, {1: closed, 2: active}, markets,
        {1: EligibilityStatus.ELIGIBLE, 2: EligibilityStatus.INELIGIBLE}, PROFILE,
    )
    assert none.preferred_variant_job_instance_id is None
