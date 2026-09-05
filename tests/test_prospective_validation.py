from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest
import yaml

from opportunity_radar.prospective_validation import (
    ARTIFACT_TYPE,
    ProspectiveProtocol,
    ProspectiveValidationError,
    calculate_prospective_metrics,
    historical_reviewed_job_ids,
    load_prospective_protocol,
    mark_historical_overlap,
    prepare_diagnostic_preview,
    render_blind_review,
    select_prospective_sample,
    semantic_cache_preflight,
    stopping_status,
)
from opportunity_radar.state_repository import SCHEMA_VERSION


ROOT = Path(__file__).parents[1]


def _protocol(**sampling_changes) -> ProspectiveProtocol:
    raw = yaml.safe_load(
        (ROOT / "experiments/phase4_prospective_validation_v1.yaml").read_text()
    )
    raw["sampling"].update(sampling_changes)
    if "strata" in sampling_changes:
        raw["sampling"]["target"] = sum(sampling_changes["strata"].values())
    return ProspectiveProtocol(raw=raw, fingerprint="fixture-protocol")


def _item(
    index: int, *, company: str | None = None, recommendation: str = "REVIEW",
    score: float = 6.0, market: str = "IN_SCOPE", members: list[int] | None = None,
    cache: str = "COMPATIBLE_SEMANTIC_CACHE_HIT",
) -> dict:
    members = members or [index]
    return {
        "cluster_id": f"cluster-{index:03d}",
        "cluster_fingerprint": f"cluster-fp-{index}",
        "company_id": company or f"company-{index % 12}",
        "company_name": company or f"Company {index % 12}",
        "member_job_instance_ids": members,
        "member_count": len(members),
        "cluster_members": [{
            "job_instance_id": member,
            "title": f"Role {index}",
            "locations": [],
            "work_mode": "unspecified",
            "canonical_url": f"https://example.test/{member}",
        } for member in members],
        "preferred_variant_job_instance_id": members[0],
        "preferred_variant_selection": {"selection_fingerprint": f"selection-{index}"},
        "job_observation_id": index + 1000,
        "content_fingerprint": f"content-{index}",
        "market_status": market,
        "normal_candidate": market != "OUT_OF_SCOPE",
        "semantic_cache_status": cache,
        "semantic_assessment_id": index + 2000 if cache.endswith("HIT") else None,
        "opportunity_assessment_id": index + 3000 if cache.endswith("HIT") else None,
        "base_composite_score": score,
        "score": score if market != "OUT_OF_SCOPE" else None,
        "tier": "HIGH" if score >= 7 else "REVIEW" if score >= 5 else "LOW",
        "recommendation": recommendation if market != "OUT_OF_SCOPE" else None,
        "title": f"Role {index}",
        "description": "Evidence",
        "locations": [],
        "work_mode": "unspecified",
        "canonical_url": f"https://example.test/{index}",
        "historical_reviewed_overlap": False,
    }


def _population() -> list[dict]:
    values = []
    for index in range(30):
        values.append(_item(index, recommendation="APPLY" if index < 10 else "REVIEW", score=8.5 - index * .08))
    for index in range(30, 65):
        values.append(_item(index, recommendation="LOW_PRIORITY", score=4.9 - (index - 30) * .05))
    for index in range(65, 80):
        values.append(_item(index, recommendation="LOW_PRIORITY", score=6.5 - (index - 65) * .1, market="OUT_OF_SCOPE"))
    return values


def _manifest(selection: dict, protocol: ProspectiveProtocol) -> dict:
    return {"selection": selection, "protocol": protocol.raw}


def _judgment(item: dict, **changes) -> dict:
    value = {
        "cluster_id": item["cluster_id"],
        "review_status": "COMPLETED",
        "attention": "YES",
        "application_intent": "APPLY",
        "market_status_human": item["market_status"],
        "preferred_variant_agreement": "NOT_APPLICABLE" if item["member_count"] == 1 else "AGREE",
        "cluster_correctness": "NOT_APPLICABLE" if item["member_count"] == 1 else "CORRECT",
        "missing_information": None,
    }
    value.update(changes)
    return value


def test_protocol_is_valid_and_frozen_to_40_cluster_design():
    protocol = load_prospective_protocol(ROOT / "experiments/phase4_prospective_validation_v1.yaml")
    assert protocol.version == "phase4-prospective-validation-v1"
    assert protocol.sampling["strata"] == {
        "TOP_ATTENTION": 15,
        "REVIEW_BOUNDARY": 10,
        "LOW_PRIORITY_CONTROL": 10,
        "MARKET_CONTROL": 5,
    }
    assert protocol.raw["human_labels"]["application_intent"][-1] == "NEED_MORE_INFO"


def test_sampling_is_deterministic_unique_and_uses_one_preferred_variant():
    protocol = _protocol()
    first = select_prospective_sample(_population(), protocol)
    second = select_prospective_sample(copy.deepcopy(_population()), protocol)
    assert first == second
    assert len(first["selected"]) == 40
    assert len({item["cluster_id"] for item in first["selected"]}) == 40
    assert all(isinstance(item["preferred_variant_job_instance_id"], int) for item in first["selected"])
    assert first["stratum_counts"] == protocol.sampling["strata"]


def test_historical_reviewed_member_excludes_whole_cluster(tmp_path):
    batch = {"selected_jobs": [{"job_instance_id": 15}, {"job_instance_id": 26}]}
    path = tmp_path / "batch.json"
    path.write_text(json.dumps(batch))
    reviewed = historical_reviewed_job_ids(path)
    population = [_item(1, members=[1, 15]), _item(2)] + _population()[2:]
    marked, summary = mark_historical_overlap(population, reviewed)
    selected = select_prospective_sample(marked, _protocol())
    assert reviewed == {15, 26}
    assert summary["excluded_cluster_count"] >= 1
    assert "cluster-001" not in {item["cluster_id"] for item in selected["selected"]}


def test_employer_cap_and_minimal_relaxation_are_explicit():
    population = [
        _item(index, company="single", recommendation="REVIEW", score=7 - index * .01)
        for index in range(50)
    ]
    # Add market controls from other employers so only the normal cap must relax.
    population += [
        _item(100 + index, company=f"market-{index}", market="OUT_OF_SCOPE")
        for index in range(5)
    ]
    result = select_prospective_sample(population, _protocol())
    assert len(result["selected"]) == 40
    assert result["normal_employer_cap_effective"] == 35
    assert result["cap_relaxations"]
    assert all(change["to_cap"] == change["from_cap"] + 1 for change in result["cap_relaxations"])


def test_stratum_fallback_and_reserve_order_are_frozen():
    population = _population()
    for item in population:
        if item["normal_candidate"]:
            item["recommendation"] = "LOW_PRIORITY"
    result = select_prospective_sample(population, _protocol())
    top = [item for item in result["selected"] if item["stratum"] == "TOP_ATTENTION"]
    assert len(top) == 15
    assert {item["selection_source"] for item in top} == {"NORMAL_REMAINDER"}
    assert all(
        item["stratum"] == stratum and item["reserve_order"] == index
        for stratum, values in result["reserves"].items()
        for index, item in enumerate(values, 1)
    )
    assert result == select_prospective_sample(copy.deepcopy(population), _protocol())


def test_market_controls_are_not_normal_metrics_and_need_more_info_is_preserved():
    protocol = _protocol()
    selection = select_prospective_sample(_population(), protocol)
    judgments = []
    for item in selection["selected"]:
        if item["stratum"] == "MARKET_CONTROL":
            judgments.append(_judgment(item, attention="NO", application_intent="DONT_APPLY"))
        elif item["stratum"] == "LOW_PRIORITY_CONTROL":
            judgments.append(_judgment(
                item, attention="NO", application_intent="NEED_MORE_INFO",
                missing_information="Work arrangement",
            ))
        else:
            judgments.append(_judgment(item))
    result = calculate_prospective_metrics(_manifest(selection, protocol), judgments)
    assert result["market_controls_excluded_from_normal_metrics"] == 5
    assert result["need_more_info_count"] == 10
    assert result["human_apply_attention_recall"] == 1.0
    assert result["top_attention_acceptance"] == 1.0


def test_need_more_info_requires_explicit_missing_information():
    protocol = _protocol()
    selection = select_prospective_sample(_population(), protocol)
    item = selection["selected"][0]
    with pytest.raises(ProspectiveValidationError, match="missing_information"):
        calculate_prospective_metrics(
            _manifest(selection, protocol),
            [_judgment(item, application_intent="NEED_MORE_INFO")],
        )


def test_metric_numerators_and_denominators_are_stable():
    protocol = _protocol()
    selection = select_prospective_sample(_population(), protocol)
    judgments = []
    for item in selection["selected"]:
        attention = "YES" if item["stratum"] in {"TOP_ATTENTION", "REVIEW_BOUNDARY"} else "NO"
        intent = "APPLY" if item["stratum"] == "TOP_ATTENTION" else "DONT_APPLY"
        judgments.append(_judgment(item, attention=attention, application_intent=intent))
    result = calculate_prospective_metrics(_manifest(selection, protocol), judgments)
    assert result["reviewed"] == 40
    assert result["human_apply_attention_recall"] == 1.0
    assert result["top_attention_acceptance"] == 1.0
    assert result["ranking_agreement"] == 1.0


def test_unavailable_does_not_become_disagreement_or_complete_the_batch():
    protocol = _protocol()
    selection = select_prospective_sample(_population(), protocol)
    item = selection["selected"][0]
    status = stopping_status(
        _manifest(selection, protocol),
        [{"cluster_id": item["cluster_id"], "review_status": "UNAVAILABLE"}],
    )
    metrics = calculate_prospective_metrics(
        _manifest(selection, protocol),
        [{"cluster_id": item["cluster_id"], "review_status": "UNAVAILABLE"}],
    )
    assert status["unavailable"] == 1
    assert status["completed"] == 0
    assert status["complete"] is False
    assert metrics["reviewed"] == 0


def test_cache_preflight_is_pure_and_cost_is_deterministic(monkeypatch):
    items = [
        _item(1),
        _item(2, cache="SEMANTIC_CACHE_MISS"),
        _item(3, cache="SEMANTICALLY_UNASSESSABLE"),
    ]
    monkeypatch.setattr("requests.post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("external call")))
    result = semantic_cache_preflight(items, 0.0026493)
    assert result == {
        "compatible_cache_hits": 1,
        "semantic_cache_misses": 1,
        "semantically_unassessable": 1,
        "semantic_assessment_required_misses": 1,
        "non_routed_cache_misses": 0,
        "expected_external_calls": 1,
        "estimated_cost_per_cache_miss_usd": 0.0026493,
        "estimated_external_cost_usd": 0.0026493,
        "external_calls_made": 0,
    }


def test_out_of_scope_cache_miss_is_classified_but_does_not_authorize_semantic_call():
    item = _item(1, market="OUT_OF_SCOPE", cache="SEMANTIC_CACHE_MISS")
    result = semantic_cache_preflight([item], 0.0026493)
    assert result["semantic_cache_misses"] == 1
    assert result["non_routed_cache_misses"] == 1
    assert result["semantic_assessment_required_misses"] == 0
    assert result["expected_external_calls"] == 0
    assert result["estimated_external_cost_usd"] == 0.0


def test_selection_signature_has_no_human_judgment_input():
    import inspect

    assert list(inspect.signature(select_prospective_sample).parameters) == ["population", "protocol"]


def test_blind_review_does_not_foreground_system_decision_evidence():
    protocol = _protocol()
    selection = select_prospective_sample(_population(), protocol)
    manifest = {
        "preview_id": "preview",
        "selection": selection,
    }
    review = render_blind_review(manifest)
    assert "DIAGNOSTIC PREVIEW ONLY" in review
    assert "system rank" not in review.lower()
    assert "recommendation" not in review.lower()
    assert "RADAR" not in review
    assert "preference effect:" not in review.lower()
    assert "### Posting variants" in review
    assert "application_intent: APPLY | DONT_APPLY | NEED_MORE_INFO" in review


def test_current_state_preview_is_read_only_and_makes_no_external_call(tmp_path, monkeypatch):
    database = ROOT / "output/opportunity_radar.sqlite3"
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    modified = database.stat().st_mtime_ns
    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("external call")),
    )
    result = prepare_diagnostic_preview(
        database,
        ROOT / "experiments/phase4_prospective_validation_v1.yaml",
        tmp_path,
        "read-only-preview",
    )
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert database.stat().st_mtime_ns == modified
    assert result["summary"]["external_calls_made"] == 0
    assert result["summary"]["is_prospective_batch"] is False


def test_private_prospective_artifacts_are_ignored_but_aggregate_is_trackable(tmp_path):
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "output/phase4_prospective/example/preview.json"],
        cwd=ROOT,
    )
    aggregate = subprocess.run(
        ["git", "check-ignore", "-q", "output/phase4_prospective/example/aggregate_summary.json"],
        cwd=ROOT,
    )
    assert ignored.returncode == 0
    assert aggregate.returncode == 1


def test_preparation_contract_does_not_change_sqlite_schema():
    assert SCHEMA_VERSION == 3
    with sqlite3.connect(ROOT / "output/opportunity_radar.sqlite3") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
    assert ARTIFACT_TYPE == "DIAGNOSTIC_PREVIEW_NOT_PROSPECTIVE_BATCH"
