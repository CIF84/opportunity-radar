from opportunity_radar.adapters.workday import WorkdayAdapter
from opportunity_radar.config import CompanyConfig

from conftest import FakeResponse, FakeSession


def test_workday_discovery_and_detail_use_split_contract(load_json):
    session = FakeSession(
        [
            FakeResponse(url="", data=load_json("workday_jobs.json")),
            FakeResponse(url="", data=load_json("workday_job.json")),
        ]
    )
    config = CompanyConfig("redhat", "Red Hat", "workday", ats_tenant="wd5|redhat|jobs")
    adapter = WorkdayAdapter(config, session)
    reference = adapter.list_jobs(config)[0]
    job = adapter.fetch_job(reference)
    assert reference.external_job_id == "R123"
    assert [location.raw for location in job.locations] == ["Prague, Czechia", "Brno, Czechia"]
    assert job.external_job_id == "R123"

