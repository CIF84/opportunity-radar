from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from opportunity_radar.phase3_config import (
    Phase3ConfigurationError,
    digest,
    load_candidate_profile,
    load_taxonomy,
)
from opportunity_radar.phase3_models import MarketAccessPolicy
from opportunity_radar.phase3_repository import Phase3Repository
from opportunity_radar.state_repository import SCHEMA_VERSION, StateRepository


ROOT = Path(__file__).parents[1]
PRIMARY_PATH = ROOT / "config/candidate.yaml"
PORTABILITY_PATH = ROOT / "config/candidate_portability_test.yaml"
TAXONOMY_PATH = ROOT / "config/taxonomy.yaml"

PHASE3_FINGERPRINTS = {
    "roman_christov": {
        "full": "3a33b922aa0cf659b4264ec0137ea6159019c5a4cff825876120a77565a812ff",
        "semantic": "6579b21e2bc22fef927ca17bdf6083b7e9a099bd5810b49528f589c83793819b",
        "scoring": "9237433984fb06f964248b199a08a6bd3ed9ddf0a0f0b341c13a0cb278db0e8a",
    },
    "portability_test_engineer": {
        "full": "7707aee320f89a2801f51284b0be3655afc8b35657dbf554a94d1e7114559e10",
        "semantic": "839e1656e7f8551f9ae285f98df7013f100e2bda9fd4e54c66aa3658d6d30d7e",
        "scoring": "9237433984fb06f964248b199a08a6bd3ed9ddf0a0f0b341c13a0cb278db0e8a",
    },
}


def _raw(path: Path = PRIMARY_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load(path: Path = PRIMARY_PATH):
    return load_candidate_profile(path, load_taxonomy(TAXONOMY_PATH))


def _write_profile(tmp_path: Path, raw: dict) -> Path:
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def test_both_profiles_use_the_same_market_access_schema():
    primary = _load(PRIMARY_PATH)
    portability = _load(PORTABILITY_PATH)

    assert primary.version == portability.version == 2
    assert isinstance(primary.market_access_policy, MarketAccessPolicy)
    assert isinstance(portability.market_access_policy, MarketAccessPolicy)
    assert set(primary.market_access_policy.payload()) == set(
        portability.market_access_policy.payload()
    )
    assert set(primary.market_access_policy.remote) == set(
        portability.market_access_policy.remote
    )


def test_phase4_policy_changes_full_fingerprint_but_preserves_phase3_identities():
    for path in (PRIMARY_PATH, PORTABILITY_PATH):
        raw = _raw(path)
        profile = _load(path)
        previous = PHASE3_FINGERPRINTS[profile.profile_id]

        assert profile.full_profile_fingerprint == digest(raw)
        assert profile.full_profile_fingerprint != previous["full"]
        assert profile.semantic_profile_fingerprint == previous["semantic"]
        assert profile.scoring_preference_fingerprint == previous["scoring"]
        assert profile.market_access_policy_fingerprint == digest(
            raw["market_access_policy"]
        )
        assert "market_access_policy" not in profile.semantic_payload()


def test_initial_candidate_policy_is_configuration_not_semantic_input():
    profile = _load()
    policy = profile.market_access_policy

    assert policy.onsite_hybrid == {
        "accepted_locations": [{"country": "Czechia", "city": "Prague"}],
        "outside_accepted_locations": "OUT_OF_SCOPE",
    }
    assert policy.remote["residence_country"] == "Czechia"
    assert policy.remote["require_confirmed_residence_compatibility"] is True
    assert policy.remote["compatible_working_time_regions"] == ["EUROPEAN_COMPATIBLE"]
    assert policy.relocation == {
        "mode": "EXCEPTIONAL_ONLY",
        "normal_shortlist": False,
    }
    assert policy.work_access_status("Czechia") == "CONFIRMED"
    assert policy.work_access_status("foreign_default") == "UNKNOWN"
    assert policy.language_support("Czech") == "NATIVE_PROFESSIONAL"
    assert policy.language_support("English") == "PROFESSIONAL"
    assert policy.language_support("Slovak") == "COMPREHENSION_ONLY"
    assert policy.language_support("French") == "NONE"
    assert policy.language_support("Japanese") == "NONE"
    assert policy.uncertainty["terminal_recommendation_cap"] == "REVIEW"
    assert policy.seniority_guard == {
        "explicit_levels": ["JUNIOR", "GRADUATE"],
        "terminal_recommendation_cap": "LOW_PRIORITY",
    }


def test_policy_only_change_has_an_independent_fingerprint(tmp_path):
    original = _load()
    raw = _raw()
    raw["profile"]["version"] += 1
    raw["market_access_policy"]["remote"]["working_hours_unspecified"] = "OUT_OF_SCOPE"
    changed = _load(_write_profile(tmp_path, raw))

    assert changed.full_profile_fingerprint != original.full_profile_fingerprint
    assert changed.market_access_policy_fingerprint != original.market_access_policy_fingerprint
    assert changed.semantic_profile_fingerprint == original.semantic_profile_fingerprint
    assert changed.scoring_preference_fingerprint == original.scoring_preference_fingerprint
    assert changed.semantic_payload() == original.semantic_payload()


def test_profile_json_preserves_market_policy_without_schema_migration(tmp_path):
    profile = _load()
    state = StateRepository(tmp_path / "state.sqlite3")

    Phase3Repository(state).save_profile(profile)
    stored = yaml.safe_load(state.rows("candidate_profiles")[0]["profile_json"])

    assert stored["market_access_policy"] == profile.market_access_policy.payload()
    assert digest(stored) == profile.full_profile_fingerprint
    with state.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 3


def test_unknown_work_access_is_distinct_from_explicit_incompatibility(tmp_path):
    unknown = _load()
    raw = _raw()
    raw["profile"]["version"] += 1
    raw["market_access_policy"]["work_access"]["foreign_default"] = "INCOMPATIBLE"
    incompatible = _load(_write_profile(tmp_path, raw))

    assert unknown.market_access_policy.work_access_status("foreign_default") == "UNKNOWN"
    assert incompatible.market_access_policy.work_access_status("foreign_default") == "INCOMPATIBLE"
    assert unknown.market_access_policy.work_access_status("Japan") is None
    assert unknown.market_access_policy_fingerprint != incompatible.market_access_policy_fingerprint
    assert unknown.semantic_profile_fingerprint == incompatible.semantic_profile_fingerprint


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda raw: raw["market_access_policy"]["languages"]["English"].update(
                support="FLUENT"
            ),
            "invalid language support",
        ),
        (
            lambda raw: raw["market_access_policy"]["work_access"].update(
                Czechia="AUTHORIZED"
            ),
            "invalid work-access status",
        ),
        (
            lambda raw: raw["market_access_policy"]["relocation"].update(
                mode="POSSIBLE"
            ),
            "invalid relocation mode",
        ),
        (
            lambda raw: raw["market_access_policy"]["seniority_guard"].update(
                explicit_levels=["ENTRY_LEVEL"]
            ),
            "invalid seniority guard level",
        ),
        (
            lambda raw: raw["market_access_policy"]["seniority_guard"].update(
                terminal_recommendation_cap="REVIEW"
            ),
            "seniority guard must be capped at LOW_PRIORITY",
        ),
        (
            lambda raw: raw["market_access_policy"]["uncertainty"].update(
                terminal_recommendation_cap="APPLY"
            ),
            "uncertain market status must be capped at REVIEW",
        ),
    ],
)
def test_market_access_controlled_values_are_validated(tmp_path, mutator, message):
    raw = deepcopy(_raw())
    mutator(raw)
    with pytest.raises(Phase3ConfigurationError, match=message):
        _load(_write_profile(tmp_path, raw))
