from __future__ import annotations

import pytest

from opportunity_radar.adapters.almacareer import AlmaCareerAdapter
from opportunity_radar.adapters.base import CountMismatchError, EmptyInventoryError
from opportunity_radar.adapters.json_feed import JsonFeedAdapter
from opportunity_radar.adapters.phenom import PhenomAdapter
from opportunity_radar.config import CompanyConfig
from conftest import FakeResponse, FakeSession


def cfg(company, adapter, options):
    return CompanyConfig(company, company.title(), adapter, endpoint_url=f"https://{company}.example/jobs", ats_tenant=f"{company}.example", options=options)


@pytest.mark.parametrize("company,widget", [("siemens", "main"), ("honeywell", "main-en"), ("csob", "main")])
def test_alma_same_code_path_and_detail(company, widget):
    html = f'<div id="vacancies" data-widget="{widget}"></div><script src="/app.js"></script>'
    api_key = "b" * 64
    js = f'"{widget}":{{"id":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa","apiKey":"{api_key}","detailPath":"/positions"}}'
    listing = {"data":{"widget":{"jobAdList":{"groupedJobAds":{"jobAds":[{"id":"1","title":"Engineer","validFrom":"2026-08-01","locations":[{"city":"Prague","country":"Czechia","region":None}],"parameters":[]}]},"paginator":{"totalNumberOfItems":1,"lastPage":1}}}}}
    detail = {"data":{"widget":{"jobAd":{"id":"1","title":"Engineer","validFrom":"2026-08-01","content":{"htmlContent":"<p>Build things</p>"},"locations":[{"city":"Prague","country":"Czechia","region":None}],"parameters":[],"employer":{"companyName":"X"}}}}}
    session = FakeSession([FakeResponse(url="", text=html), FakeResponse(url="", text=js), FakeResponse(url="", data=listing), FakeResponse(url="", data=detail)])
    adapter = AlmaCareerAdapter(cfg(company, "almacareer", {}), session)
    refs = adapter.list_jobs(adapter.config)
    assert adapter.fetch_job(refs[0]).locations[0].raw == "Prague, Czechia"


@pytest.mark.parametrize("company,item_path", [("allegro", "offers"), ("schneider", "jobs")])
def test_json_feed_same_code_path(company, item_path):
    item = {"id":"1", "title":"Engineer", "url":"https://example/jobs/1", "place":"Prague"}
    payload = {item_path:[item], "count":1, "pages":1}
    options = {"items_path":item_path, "pagination":{"count_path":"count","pages_path":"pages"}, "fields":{"external_job_id":"id","title":"title","canonical_url":"url","locations":"place"}}
    adapter = JsonFeedAdapter(cfg(company, "json_feed", options), FakeSession([FakeResponse(url="", data=payload)]))
    refs = adapter.list_jobs(adapter.config)
    assert adapter.fetch_job(refs[0]).title == "Engineer"


def test_json_feed_count_mismatch_is_failure():
    options = {"items_path":"jobs", "pagination":{"count_path":"count","pages_path":"pages"}, "fields":{"title":"title","canonical_url":"url"}}
    payload = {"jobs":[{"title":"A","url":"https://x/a"}], "count":2, "pages":1}
    adapter = JsonFeedAdapter(cfg("x", "json_feed", options), FakeSession([FakeResponse(url="", data=payload)]))
    with pytest.raises(CountMismatchError):
        adapter.list_jobs(adapter.config)


@pytest.mark.parametrize("company", ["roche", "cisco"])
def test_phenom_same_code_path(company):
    payload = {"refineSearch":{"status":200,"totalHits":1,"data":{"jobs":[{"jobId":"7","title":"Data Lead","location":"Prague","postedDate":"2026-08-01"}]}}}
    options = {"canonical_url_template":f"https://{company}.example/job/{{jobId}}/{{title_slug}}"}
    adapter = PhenomAdapter(cfg(company, "phenom", options), FakeSession([FakeResponse(url="", data=payload)]))
    refs = adapter.list_jobs(adapter.config)
    assert adapter.fetch_job(refs[0]).canonical_url.endswith("/7/data-lead")


@pytest.mark.parametrize("adapter_cls,adapter_name,payload,options", [
    (JsonFeedAdapter,"json_feed",{"jobs":[],"count":0,"pages":0},{"items_path":"jobs","pagination":{"count_path":"count","pages_path":"pages"},"fields":{}}),
    (PhenomAdapter,"phenom",{"refineSearch":{"status":200,"totalHits":0,"data":{"jobs":[]}}},{"canonical_url_template":"https://x/{jobId}"}),
])
def test_explicit_zero_is_empty(adapter_cls, adapter_name, payload, options):
    adapter = adapter_cls(cfg("x", adapter_name, options), FakeSession([FakeResponse(url="", data=payload)]))
    with pytest.raises(EmptyInventoryError):
        adapter.list_jobs(adapter.config)
