import pytest

from opportunity_radar.config import CompanyConfig, ConfigurationError, load_companies


def test_workday_configuration_is_validated_before_network():
    with pytest.raises(ConfigurationError, match="host\\|tenant\\|site"):
        CompanyConfig.from_dict(
            {"company_id": "x", "company_name": "X", "adapter": "workday", "ats_tenant": "bad"}
        )


def test_runtime_config_is_independent_from_research_csv():
    companies = load_companies("config/companies.yaml")
    assert len(companies) == 15
    assert {company.adapter for company in companies} == {
        "workday", "greenhouse", "almacareer", "successfactors", "generic_html"
    }

