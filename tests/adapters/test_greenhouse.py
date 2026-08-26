from opportunity_radar.adapters.greenhouse import GreenhouseAdapter
from opportunity_radar.config import CompanyConfig
from opportunity_radar.models import WorkMode

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
    assert references[0].listing_facts.title == "Analyst"
    assert references[0].listing_facts.locations[0].raw == "Prague"
    assert references[0].listing_facts.source_updated_at.isoformat() == "2026-08-01T12:00:00+00:00"
    job = adapter.fetch_job(references[0])
    assert references[0].external_job_id == "123"
    assert len(job.locations) == 2
    assert len({job.external_job_id}) == 1
    assert job.description == "Build useful systems."


def test_greenhouse_listing_detects_explicit_remote_work_mode():
    listing = {"jobs": [{"id": 1, "absolute_url": "https://example.test/1", "title": "Role", "location": {"name": "Germany - Remote"}}]}
    config = CompanyConfig("pure", "Pure", "greenhouse", ats_tenant="pure")
    reference = GreenhouseAdapter(config, FakeSession([FakeResponse(url="", data=listing)])).list_jobs(config)[0]
    assert reference.listing_facts.locations[0].raw == "Germany - Remote"
    assert reference.listing_facts.work_mode is WorkMode.REMOTE
