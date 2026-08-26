from opportunity_radar.adapters.workday import WorkdayAdapter
from opportunity_radar.config import CompanyConfig
from opportunity_radar.models import WorkMode

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
    assert reference.listing_facts.title == "Engineer"
    assert reference.listing_facts.locations == ()
    job = adapter.fetch_job(reference)
    assert reference.external_job_id == "R123"
    assert [location.raw for location in job.locations] == ["Prague, Czechia", "Brno, Czechia"]
    assert job.external_job_id == "R123"


def test_workday_read_only_listing_schema_diagnostic(load_json):
    session = FakeSession([FakeResponse(url="", data=load_json("workday_jobs.json"))])
    config = CompanyConfig("redhat", "Red Hat", "workday", ats_tenant="wd5|redhat|jobs")
    adapter = WorkdayAdapter(config, session)
    adapter.enable_listing_schema_diagnostics(1)
    adapter.list_jobs(config)
    sample = adapter.listing_schema_samples[0]
    assert sample["keys"] == ["bulletFields", "externalPath", "title"]
    assert sample["types"]["title"] == "str"
    assert sample["sample"]["title"] == "Engineer"
    assert adapter.listing_response_diagnostics[0]["keys"] == ["jobPostings", "total"]
    assert adapter.listing_response_diagnostics[0]["facets"] is None


def test_workday_read_only_response_diagnostic_captures_bounded_facets():
    payload = {
        "total": 1,
        "facets": [{"facetParameter": "locations", "values": [
            {"id": "czech-id", "descriptor": "Czechia", "count": 1},
        ]}],
        "jobPostings": [
            {"title": "Role", "externalPath": "/job/1", "bulletFields": ["1"]},
        ],
    }
    config = CompanyConfig("acme", "Acme", "workday", ats_tenant="wd5|acme|jobs")
    adapter = WorkdayAdapter(config, FakeSession([FakeResponse(url="", data=payload)]))
    adapter.enable_listing_schema_diagnostics(1)
    adapter.list_jobs(config)
    diagnostic = adapter.listing_response_diagnostics[0]
    assert diagnostic["facets"][0]["facetParameter"] == "locations"
    assert diagnostic["facets"][0]["values"][0]["id"] == "czech-id"
    assert diagnostic["applied_facets"] == {}


def test_workday_listing_facts_use_locations_text_and_remote_type():
    payload = {"total": 2, "jobPostings": [
        {"title": "Czech Role", "externalPath": "/job/1", "bulletFields": ["1"], "locationsText": "Prague, Czechia", "remoteType": "Hybrid"},
        {"title": "Remote Role", "externalPath": "/job/2", "bulletFields": ["2"], "locationsText": "2 Locations", "remoteType": "Remote"},
    ]}
    config = CompanyConfig("redhat", "Red Hat", "workday", ats_tenant="wd5|redhat|jobs")
    references = WorkdayAdapter(config, FakeSession([FakeResponse(url="", data=payload)])).list_jobs(config)
    assert references[0].listing_facts.locations[0].raw == "Prague, Czechia"
    assert references[0].listing_facts.work_mode is WorkMode.HYBRID
    assert references[1].listing_facts.locations[0].raw == "2 Locations"
    assert references[1].listing_facts.work_mode is WorkMode.REMOTE


def test_workday_listing_detects_explicit_remote_in_locations_text():
    payload = {"total": 1, "jobPostings": [
        {"title": "Role", "externalPath": "/job/1", "bulletFields": ["1"], "locationsText": "United States - Texas - Remote"},
    ]}
    config = CompanyConfig("pfizer", "Pfizer", "workday", ats_tenant="wd1|pfizer|jobs")
    reference = WorkdayAdapter(config, FakeSession([FakeResponse(url="", data=payload)])).list_jobs(config)[0]
    assert reference.listing_facts.work_mode is WorkMode.REMOTE
