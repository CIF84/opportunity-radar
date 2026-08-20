from opportunity_radar.adapters.generic import GenericHtmlAdapter
from opportunity_radar.config import CompanyConfig
from opportunity_radar.models import WorkMode

from conftest import FakeResponse, FakeSession


def test_declarative_generic_adapter_and_json_ld_detail(load_text):
    session = FakeSession(
        [
            FakeResponse(url="https://example.test/careers", text=load_text("generic_list.html")),
            FakeResponse(url="https://example.test/jobs/5678", text=load_text("generic_detail.html")),
        ]
    )
    config = CompanyConfig(
        "acme",
        "Acme",
        "generic_html",
        endpoint_url="https://example.test/careers",
        options={
            "selectors": {
                "job_container": ".job",
                "title": ".title",
                "url": "a.title",
                "location": ".location",
            }
        },
    )
    adapter = GenericHtmlAdapter(config, session)
    reference = adapter.list_jobs(config)[0]
    job = adapter.fetch_job(reference)
    assert job.external_job_id == "5678"
    assert len(job.locations) == 2
    assert job.work_mode is WorkMode.REMOTE
    assert job.description == "Analyze data."

