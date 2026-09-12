from __future__ import annotations

from pathlib import Path

import pytest

from conftest import FakeResponse, FakeSession
from opportunity_radar.adapters.json_feed import JsonFeedAdapter
from opportunity_radar.mews_onboarding import (
    MewsOnboardingError,
    load_mews_onboarding_config,
    zero_detail_summary,
)
from opportunity_radar.scope_selection import load_market_scope
from opportunity_radar.state_runner import detail_requires_network


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/mews_nested_feed_v1.yaml"


def test_mews_experiment_config_is_bounded_and_declarative():
    config = load_mews_onboarding_config(CONFIG)
    assert config.company.company_id == "mews"
    assert config.company.options["nested_items"]["parent_context"] == {
        "department": "name"
    }
    assert config.raw["safety"]["zero_detail_reruns"] == 2
    assert config.raw["privacy"]["detailed_artifact"] == "PRIVATE_LOCAL"
    assert detail_requires_network(config.company)


def test_zero_detail_summary_requires_equal_complete_identity_sets(load_json):
    config = load_mews_onboarding_config(CONFIG)
    payload = load_json("mews_nested_feed.json")
    first = JsonFeedAdapter(
        config.company, FakeSession([FakeResponse(url="", data=payload)]),
    ).list_jobs(config.company)
    second = JsonFeedAdapter(
        config.company, FakeSession([FakeResponse(url="", data=payload)]),
    ).list_jobs(config.company)
    result = zero_detail_summary(
        first, second, load_market_scope(ROOT / "config/market_scope.yaml")
    )
    assert result == {
        "inventory": 2,
        "unique_external_ids": 2,
        "unique_canonical_urls": 2,
        "deterministic_rerun_equal": True,
        "detail_calls": 0,
        "phase2_writes": 0,
        "market_scope_counts": {
            "SELECT_IN_SCOPE": 1,
            "SKIP_EXPLICITLY_OUT_OF_SCOPE": 1,
        },
    }


def test_zero_detail_summary_rejects_changed_rerun(load_json):
    config = load_mews_onboarding_config(CONFIG)
    payload = load_json("mews_nested_feed.json")
    first = JsonFeedAdapter(
        config.company, FakeSession([FakeResponse(url="", data=payload)]),
    ).list_jobs(config.company)
    changed = load_json("mews_nested_feed.json")
    changed[0]["jobs"][0]["title"] = "Changed"
    second = JsonFeedAdapter(
        config.company, FakeSession([FakeResponse(url="", data=changed)]),
    ).list_jobs(config.company)
    with pytest.raises(MewsOnboardingError, match="not deterministic"):
        zero_detail_summary(
            first, second, load_market_scope(ROOT / "config/market_scope.yaml")
        )
