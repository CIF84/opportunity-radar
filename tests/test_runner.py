from opportunity_radar.config import CompanyConfig
from opportunity_radar.runner import ingest_company


def test_employer_failure_is_isolated(monkeypatch):
    class BrokenAdapter:
        def list_jobs(self, config):
            raise RuntimeError("source changed")

    monkeypatch.setattr("opportunity_radar.runner.AdapterRegistry.create", lambda config: BrokenAdapter())
    result = ingest_company(CompanyConfig("broken", "Broken", "unused"))
    assert result.status == "FAIL"
    assert "source changed" in result.error

