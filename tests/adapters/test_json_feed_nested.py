from __future__ import annotations

import copy
from pathlib import Path

import pytest

from conftest import FakeResponse, FakeSession
from opportunity_radar.adapters.base import CountMismatchError, SchemaMismatchError
from opportunity_radar.adapters.json_feed import JsonFeedAdapter
from opportunity_radar.config import CompanyConfig
from opportunity_radar.scope_selection import listing_facts_fingerprint


def _config() -> CompanyConfig:
    return CompanyConfig.from_dict({
        "company_id": "nested_example",
        "company_name": "Nested Example",
        "adapter": "json_feed",
        "endpoint_url": "https://example.test/api/careers",
        "options": {
            "nested_items": {
                "groups_path": "",
                "items_path": "jobs",
                "group_count_path": "jobCount",
                "parent_context": {"department": "name"},
            },
            "fields": {
                "external_job_id": "item.id",
                "title": "item.title",
                "canonical_url": "item.url",
                "locations": "item.locations",
                "source_updated_at": "item.updatedAt",
                "department": "parent.department",
            },
        },
    })


def _adapter(payload) -> JsonFeedAdapter:
    return JsonFeedAdapter(
        _config(), FakeSession([FakeResponse(url="", data=payload)]),
    )


def test_nested_records_flatten_multiple_groups_and_inherit_parent(load_json):
    refs = _adapter(load_json("json_feed_nested.json")).list_jobs(_config())
    assert [ref.external_job_id for ref in refs] == ["10", "20", "30"]
    assert [ref.listing_facts.department for ref in refs] == [
        "Operations", "Operations", "Product",
    ]
    assert refs[0].listing_facts.work_mode.value == "remote"
    assert refs[0].listing_facts.source_updated_at.isoformat() == "2026-09-09T10:00:00+00:00"
    assert _adapter(load_json("json_feed_nested.json")).fetch_job(refs[2]).department == "Product"


def test_nested_order_and_fingerprints_ignore_object_key_order(load_json):
    payload = load_json("json_feed_nested.json")
    reordered = [
        {key: group[key] for key in reversed(list(group))}
        for group in reversed(copy.deepcopy(payload))
    ]
    for group in reordered:
        group["jobs"] = [
            {key: job[key] for key in reversed(list(job))}
            for job in reversed(group["jobs"])
        ]
    first = _adapter(payload).list_jobs(_config())
    second = _adapter(reordered).list_jobs(_config())
    assert [ref.external_job_id for ref in first] == [ref.external_job_id for ref in second]
    assert [listing_facts_fingerprint(ref.listing_facts) for ref in first] == [
        listing_facts_fingerprint(ref.listing_facts) for ref in second
    ]


@pytest.mark.parametrize("group", [
    {"name": "Missing", "jobCount": 0},
    {"name": "Malformed", "jobCount": 1, "jobs": {}},
])
def test_nested_missing_or_malformed_child_collection_fails(group):
    with pytest.raises(SchemaMismatchError, match="nested child path"):
        _adapter([group]).list_jobs(_config())


def test_nested_group_count_mismatch_fails():
    group = {"name": "Mismatch", "jobCount": 2, "jobs": []}
    with pytest.raises(CountMismatchError, match="expected 2 jobs"):
        _adapter([group]).list_jobs(_config())


def test_nested_duplicate_child_identity_fails(load_json):
    payload = load_json("json_feed_nested.json")
    payload[1]["jobs"][0]["id"] = 20
    with pytest.raises(SchemaMismatchError, match="duplicate nested job identity 20"):
        _adapter(payload).list_jobs(_config())


def test_nested_configured_parent_path_failure_is_visible(load_json):
    config = _config()
    config.options["nested_items"]["parent_context"]["department"] = "missing"
    adapter = JsonFeedAdapter(
        config, FakeSession([FakeResponse(url="", data=load_json("json_feed_nested.json"))]),
    )
    with pytest.raises(SchemaMismatchError, match="nested parent path 'missing'"):
        adapter.list_jobs(config)


def test_flat_feed_behavior_remains_unchanged():
    config = CompanyConfig.from_dict({
        "company_id": "flat_example",
        "company_name": "Flat Example",
        "adapter": "json_feed",
        "endpoint_url": "https://example.test/jobs",
        "options": {
            "items_path": "jobs",
            "pagination": {"count_path": "count", "pages_path": "pages"},
            "fields": {
                "external_job_id": "id", "title": "title",
                "canonical_url": "url", "locations": "locations",
            },
        },
    })
    payload = {
        "jobs": [{"id": "1", "title": "Analyst", "url": "https://example.test/1", "locations": ["Prague"]}],
        "count": 1,
        "pages": 1,
    }
    refs = JsonFeedAdapter(config, FakeSession([FakeResponse(url="", data=payload)])).list_jobs(config)
    assert [(ref.external_job_id, ref.listing_facts.title) for ref in refs] == [("1", "Analyst")]


def test_bounded_mews_shape_uses_only_declarative_contract(load_json):
    config = _config()
    adapter = JsonFeedAdapter(
        config, FakeSession([FakeResponse(url="", data=load_json("mews_nested_feed.json"))]),
    )
    refs = adapter.list_jobs(config)
    assert len(refs) == 2
    assert refs[0].canonical_url.startswith("https://www.mews.com/en/careers/jobs/")
    assert refs[1].listing_facts.locations[0].raw == "Czechia; Spain; United Kingdom"
    assert all(adapter.fetch_job(ref).description is None for ref in refs)


def test_shared_adapter_contains_no_mews_identity_branch():
    source = Path(JsonFeedAdapter.__module__.replace(".", "/") + ".py")
    if not source.exists():
        source = Path("src/opportunity_radar/adapters/json_feed.py")
    assert "mews" not in source.read_text(encoding="utf-8").casefold()


def test_optional_json_detail_selectors_retrieve_usable_description(load_json):
    config = _config()
    config.options["detail_selectors"] = {
        "title": "h1", "description": ".job-content",
    }
    session = FakeSession([
        FakeResponse(url="", data=load_json("mews_nested_feed.json")),
        FakeResponse(
            url="",
            text='<html><h1>Current title</h1><main class="job-content"><p>Own the product strategy.</p></main></html>',
        ),
    ])
    adapter = JsonFeedAdapter(config, session)
    reference = adapter.list_jobs(config)[0]
    job = adapter.fetch_job(reference)
    assert job.title == "Current title"
    assert job.description == "Own the product strategy."


def test_configured_json_detail_selector_failure_is_visible(load_json):
    config = _config()
    config.options["detail_selectors"] = {"description": ".missing"}
    session = FakeSession([
        FakeResponse(url="", data=load_json("mews_nested_feed.json")),
        FakeResponse(url="", text="<html><main>Different contract</main></html>"),
    ])
    adapter = JsonFeedAdapter(config, session)
    reference = adapter.list_jobs(config)[0]
    with pytest.raises(SchemaMismatchError, match="detail description selector missing"):
        adapter.fetch_job(reference)
