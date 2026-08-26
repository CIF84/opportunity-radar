from opportunity_radar.adapters.generic import GenericHtmlAdapter
from opportunity_radar.adapters.base import PaginationCapError
from opportunity_radar.config import CompanyConfig
from opportunity_radar.models import WorkMode

from conftest import FakeResponse, FakeSession
import pytest


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
    assert reference.listing_facts.title == "Data Analyst"
    assert reference.listing_facts.locations[0].raw == "Prague, Czechia"
    job = adapter.fetch_job(reference)
    assert job.external_job_id == "5678"
    assert len(job.locations) == 2
    assert job.work_mode is WorkMode.REMOTE
    assert job.description == "Analyze data."


def _page(job_id=None):
    body = "" if job_id is None else f'<div class="job"><a class="title" href="/jobs/{job_id}">Role {job_id}</a><span class="location">Prague</span></div>'
    return FakeResponse(url="https://example.test/careers", text=f"<html><body>{body}</body></html>")


def _paginated_config(max_pages=2):
    return CompanyConfig(
        "acme", "Acme", "generic_html", endpoint_url="https://example.test/careers",
        options={
            "selectors": {"job_container": ".job", "title": ".title", "url": "a.title", "location": ".location"},
            "pagination": {"param": "startrow", "start": 0, "step": 25, "safety_max_pages": max_pages},
        },
    )


def test_pagination_cap_requires_empty_probe_to_prove_completeness():
    config = _paginated_config()
    adapter = GenericHtmlAdapter(config, FakeSession([_page("1001"), _page("1002"), _page()]))
    assert len(adapter.list_jobs(config)) == 2


def test_nonempty_pagination_probe_is_explicit_incomplete_failure():
    config = _paginated_config()
    adapter = GenericHtmlAdapter(config, FakeSession([_page("1001"), _page("1002"), _page("1003")]))
    with pytest.raises(PaginationCapError, match="probe page is non-empty"):
        adapter.list_jobs(config)


def test_legacy_normal_page_cap_no_longer_truncates_inventory():
    config = CompanyConfig(
        "acme", "Acme", "generic_html", endpoint_url="https://example.test/careers",
        options={
            "selectors": {"job_container": ".job", "title": ".title", "url": "a.title", "location": ".location"},
            "pagination": {"param": "startrow", "start": 0, "step": 25, "max_pages": 2},
        },
    )
    adapter = GenericHtmlAdapter(
        config, FakeSession([_page("1001"), _page("1002"), _page("1003"), _page()]),
    )
    assert len(adapter.list_jobs(config)) == 3


@pytest.mark.parametrize(
    "first_url,next_href,second_url",
    [
        ("https://example.test/go/Czech/1/", "/go/Czech/1/25/?q=", "https://example.test/go/Czech/1/25/?q="),
        ("https://example.test/search/", "?startrow=25", "https://example.test/search/?startrow=25"),
    ],
)
def test_discovered_offset_link_pagination_supports_path_and_query_offsets(first_url, next_href, second_url):
    def page(job_id, next_link=""):
        return FakeResponse(
            url=first_url if job_id == "1" else second_url,
            text=(
                f'<div class="job"><a class="title" href="/jobs/{job_id}">Role</a>'
                f'<span class="location">Prague</span></div>{next_link}'
            ),
        )

    config = CompanyConfig(
        "sf", "SF", "generic_html", endpoint_url=first_url,
        options={
            "selectors": {"job_container": ".job", "title": ".title", "url": "a.title", "location": ".location"},
            "pagination": {"mode": "discovered_offset_link", "safety_max_pages": 10},
        },
    )
    session = FakeSession([
        page("1", f'<a href="{next_href}">2</a>'),
        page("2", '<a href="?startrow=0">1</a>'),
    ])
    references = GenericHtmlAdapter(config, session).list_jobs(config)
    assert [reference.canonical_url for reference in references] == [
        "https://example.test/jobs/1", "https://example.test/jobs/2",
    ]
    assert session.responses == []


def test_bounded_successfactors_source_diagnostics_capture_public_contract():
    html = """<html><body data-total-count="123">
      <form><input type="hidden" name="searchToken" value="secret-value">
      <select name="locationsearch"><option value="CZ">Czechia</option></select></form>
      <div id="search-results-count">123 results</div>
      <a class="pagination-next" href="?startrow=25">Next</a>
      <div class="job"><a class="title" href="/job/Role/1001">Role</a><span class="location">Prague, CZ, 110 00</span></div>
      <script>window.endpoint = "/api/search/jobs?token=public-value";</script>
    </body></html>"""
    config = CompanyConfig(
        "sf", "SF", "generic_html", endpoint_url="https://example.test/search",
        options={"selectors": {"job_container": ".job", "title": ".title", "url": "a.title", "location": ".location"}},
    )
    adapter = GenericHtmlAdapter(config, FakeSession([FakeResponse(url="https://example.test/search", text=html)]))
    adapter.enable_source_diagnostics(1)
    adapter.list_jobs(config)
    diagnostic = adapter.source_diagnostics[0]
    assert diagnostic["response_url"] == "https://example.test/search"
    assert diagnostic["pagination_links"][0]["href"].endswith("?startrow=25")
    assert diagnostic["hidden_fields"][0]["value"] == "<redacted>"
    assert diagnostic["total_result_candidates"]
    assert diagnostic["location_country_filter_controls"][0]["name"] == "locationsearch"
    assert diagnostic["relevant_data_attributes"][0]["attributes"]["data-total-count"] == "123"
    assert "token=%3Credacted%3E" in diagnostic["referenced_public_endpoints"][0]
