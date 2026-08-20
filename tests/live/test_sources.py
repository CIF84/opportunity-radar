import pytest

from opportunity_radar.config import load_companies
from opportunity_radar.runner import ingest_company


@pytest.mark.live
@pytest.mark.parametrize("config", load_companies("config/companies.yaml"), ids=lambda c: c.company_id)
def test_public_source(config):
    result = ingest_company(config, max_jobs=1)
    assert result.status in {"PASS", "PARTIAL"}, result.error
    assert result.references_found > 0
    assert result.jobs_normalized > 0

