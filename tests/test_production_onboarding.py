from pathlib import Path

import pytest

from opportunity_radar.config import ConfigurationError, load_companies
from opportunity_radar.production_onboarding import coverage_delta
from opportunity_radar.state_runner import detail_requires_network
from opportunity_radar.state_runner import select_company_configs


ROOT = Path(__file__).resolve().parents[1]


def test_spec015_adds_only_approved_generic_sources():
    configs = load_companies(ROOT / "config/companies.yaml")
    assert len(configs) == 22
    assert [item.company_id for item in configs[-4:-1]] == ["keboola", "commerzbank", "kpmg"]
    assert configs[-1].company_id == "mews"
    assert detail_requires_network(configs[-1])
    assert not detail_requires_network(next(item for item in configs if item.company_id == "allegro"))
    assert [item.adapter for item in configs[-4:-1]] == ["generic_html", "almacareer", "almacareer"]


def test_bounded_source_selection_never_widens_and_all_source_is_unchanged():
    configs = load_companies(ROOT / "config/companies.yaml")
    assert select_company_configs(configs, []) is configs
    selected = select_company_configs(configs, ["kpmg", "keboola"])
    assert [item.company_id for item in selected] == ["keboola", "kpmg"]
    with pytest.raises(ConfigurationError, match="unknown requested"):
        select_company_configs(configs, ["typo"])


def test_coverage_delta_is_deterministic():
    concentration = {key: {"total": 10, "employer_count": 2, "top_1_share": .6, "top_3_share": 1.0, "top_5_share": 1.0, "hhi": 5200.0, "effective_employers": 1.923} for key in ("all_observed_inventory", "usable_active_detail", "market_routed_candidate_population")}
    before = {"portfolio": {"summary": {"configured_employer_count": 2, "concentration": concentration}}, "population_metadata": {"active_job_count": 10, "active_usable_detail_count": 10, "cluster_count": 10, "normal_candidate_count": 8}, "target_role_summary": {"unique_cluster_count": 2, "unique_routed_cluster_count": 1, "title_supported_unique_cluster_count": 1, "description_only_unique_cluster_count": 1}}
    after = {"portfolio": {"summary": {"configured_employer_count": 3, "concentration": concentration}}, "population_metadata": {"active_job_count": 12, "active_usable_detail_count": 12, "cluster_count": 12, "normal_candidate_count": 10}, "target_role_summary": {"unique_cluster_count": 3, "unique_routed_cluster_count": 2, "title_supported_unique_cluster_count": 2, "description_only_unique_cluster_count": 1}}
    result = coverage_delta(before, after)
    assert result["configured_employers"]["delta"] == 1
    assert result["opportunity_coverage"]["cluster_count"]["delta"] == 2
