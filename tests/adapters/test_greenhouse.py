from opportunity_radar.adapters.greenhouse import GreenhouseAdapter
from opportunity_radar.config import CompanyConfig

from conftest import FakeResponse, FakeSession


def test_greenhouse_discovery_and_detail_preserve_one_multilocation_job(load_json):
    session = FakeSession(
        [
            FakeResponse(url="", data=load_json("greenhouse_jobs.json")),
            FakeResponse(url="", data=load_json("greenhouse_job.json")),
        ]
    )
    config = CompanyConfig("pure", "Pure", "greenhouse", ats_tenant="pure")
    adapter = GreenhouseAdapter(config, session)
    references = adapter.list_jobs(config)
    job = adapter.fetch_job(references[0])
    assert references[0].external_job_id == "123"
    assert len(job.locations) == 2
    assert len({job.external_job_id}) == 1
    assert job.description == "Build useful systems."

