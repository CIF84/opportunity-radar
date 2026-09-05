from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
from pathlib import Path

import pytest

from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.prospective_validation import load_prospective_protocol
from opportunity_radar.semantic_allocation_audit import load_allocation_audit_config
from opportunity_radar.semantic_allocation_audit import build_presemantic_audit_population
from opportunity_radar.semantic_worthiness_validation import (
    PRIMARY_LABELS,
    SemanticWorthinessError,
    append_replacement,
    append_worthiness_judgment,
    calculate_worthiness_metrics,
    effective_selected_items,
    load_jsonl,
    load_worthiness_protocol,
    prepare_worthiness_validation,
    render_blind_review,
    select_worthiness_sample,
)


ROOT = Path(__file__).resolve().parents[1]


def _row(index: int, stratum: str, company: str | None = None) -> dict:
    company = company or f"company-{index % 12:02d}"
    return {
        "cluster_id": f"cluster-{stratum.lower()}-{index:03d}",
        "cluster_fingerprint": f"cluster-fingerprint-{index}",
        "company_id": company,
        "company_name": f"Employer {company}",
        "member_job_instance_ids": [index],
        "preferred_variant_job_instance_id": index,
        "title": f"Role {index}",
        "description": "A sufficiently detailed public vacancy description for review. " * 8,
        "locations": [{"raw": "Prague, Czechia", "city": "Prague", "country": "Czechia", "region": None}],
        "work_mode": "hybrid",
        "employment_type": "Full time",
        "department": "Operations",
        "canonical_url": f"https://example.test/jobs/{index}",
        "market_status": "IN_SCOPE",
        "market_assessment": {"status": "IN_SCOPE", "reasons": ["PRAGUE"]},
        "semantic_cache_status": "SEMANTIC_CACHE_MISS",
        "semantic_assessment_id": None,
        "opportunity_assessment_id": None,
        "score": None,
        "recommendation": None,
        "presemantic_triage": {
            "state": stratum,
            "reasons": ["FIXTURE"],
            "positive_concepts": [],
            "positive_title_concepts": [],
            "positive_description_concepts": [],
            "obvious_role_families": [],
            "matched_preference_concepts": [],
            "deterministic_feature_concepts": [],
            "sparse_description": False,
            "junior_or_graduate": False,
        },
    }


def _population(per_stratum: int = 30) -> list[dict]:
    rows = []
    for offset, stratum in enumerate((
        "SEMANTIC_PRIORITY", "SEMANTIC_OPTIONAL", "SEMANTIC_DEFER",
    )):
        rows.extend(_row(offset * 1000 + index, stratum) for index in range(per_stratum))
    return rows


def _enriched_manifest(selection: dict, protocol=None) -> dict:
    protocol = protocol or load_worthiness_protocol(ROOT / "experiments/semantic_compute_worthiness_v1.yaml")
    population = {row["cluster_id"]: row for row in _population()}

    def enrich(item):
        row = population[item["cluster_id"]]
        return {
            **item,
            "cluster_fingerprint": row["cluster_fingerprint"],
            "company_name": row["company_name"],
            "title": row["title"],
            "description_excerpt": row["description"][:500],
            "locations": row["locations"],
            "work_mode": row["work_mode"],
            "employment_type": row["employment_type"],
            "department": row["department"],
            "canonical_url": row["canonical_url"],
            "market_status": row["market_status"],
            "evidence_missing": [],
        }

    return {
        "preparation_id": "prep-test",
        "experiment_id": protocol.experiment_id,
        "protocol_fingerprint": protocol.fingerprint,
        "human_labels": protocol.raw["human_labels"],
        "privacy": protocol.raw["privacy"],
        "sample": {
            "selection_fingerprint": selection["selection_fingerprint"],
            "selected": [enrich(item) for item in selection["selected"]],
            "reserves": {
                key: [enrich(item) for item in values]
                for key, values in selection["reserves"].items()
            },
        },
        "population": {
            "projected_cache_misses_by_stratum": {
                "SEMANTIC_PRIORITY": 10,
                "SEMANTIC_OPTIONAL": 20,
                "SEMANTIC_DEFER": 5,
            },
            "estimated_cost_per_cache_miss_usd": 0.002,
        },
    }


def test_protocol_is_valid_and_frozen_to_60_cluster_design():
    protocol = load_worthiness_protocol(ROOT / "experiments/semantic_compute_worthiness_v1.yaml")
    assert protocol.version == "semantic-compute-worthiness-v1"
    assert protocol.sampling["target"] == 60
    assert protocol.sampling["strata"] == {
        "SEMANTIC_PRIORITY": 20,
        "SEMANTIC_OPTIONAL": 20,
        "SEMANTIC_DEFER": 20,
    }
    assert set(protocol.raw["human_labels"]["primary"]) == PRIMARY_LABELS


def test_selection_is_deterministic_cache_blind_and_semantic_blind():
    protocol = load_worthiness_protocol()
    population = _population()
    changed = copy.deepcopy(population)
    for index, row in enumerate(changed):
        row["semantic_cache_status"] = "COMPATIBLE_SEMANTIC_CACHE_HIT"
        row["semantic_assessment_id"] = index
        row["score"] = 10 - index / 100
        row["recommendation"] = "APPLY"
        row["semantic_payload"] = {"secret": index}
    first = select_worthiness_sample(population, protocol)
    second = select_worthiness_sample(changed, protocol)
    assert first == second
    assert len(first["selected"]) == 60
    assert len({item["cluster_id"] for item in first["selected"]}) == 60
    assert list(inspect.signature(select_worthiness_sample).parameters) == ["population", "protocol"]
    source = inspect.getsource(build_presemantic_audit_population)
    assert "load_judgments" not in source
    assert "assessment_json" not in source


def test_employer_cap_review_mix_and_reserves_are_frozen():
    protocol = load_worthiness_protocol()
    result = select_worthiness_sample(_population(), protocol)
    assert max(result["employer_counts"].values()) <= 5
    assert not result["cap_relaxations"]
    assert {key: len(value) for key, value in result["reserves"].items()} == {
        "SEMANTIC_PRIORITY": 5,
        "SEMANTIC_OPTIONAL": 5,
        "SEMANTIC_DEFER": 5,
    }
    review_strata = [item["stratum"] for item in result["selected"]]
    assert sum(left != right for left, right in zip(review_strata, review_strata[1:])) > 2
    assert result == select_worthiness_sample(copy.deepcopy(_population()), protocol)


def test_defer_shortfall_reallocates_only_to_optional():
    protocol = load_worthiness_protocol()
    population = [
        *[_row(index, "SEMANTIC_PRIORITY") for index in range(30)],
        *[_row(1000 + index, "SEMANTIC_OPTIONAL") for index in range(45)],
        *[_row(2000 + index, "SEMANTIC_DEFER") for index in range(5)],
    ]
    result = select_worthiness_sample(population, protocol)
    assert result["defer_shortfall"] == 15
    assert result["effective_strata"] == {
        "SEMANTIC_PRIORITY": 20,
        "SEMANTIC_OPTIONAL": 35,
        "SEMANTIC_DEFER": 5,
    }


def test_joint_cap_solver_finds_minimum_then_balances_abundant_strata():
    protocol = load_worthiness_protocol()
    companies = [f"company-{index:02d}" for index in range(17)]
    population = []
    defer_distribution = {
        "company-00": 16, "company-01": 5, "company-02": 4,
        "company-03": 1, "company-04": 1,
    }
    index = 0
    for company, count in defer_distribution.items():
        for _ in range(count):
            population.append(_row(index, "SEMANTIC_DEFER", company))
            index += 1
    for stratum in ("SEMANTIC_PRIORITY", "SEMANTIC_OPTIONAL"):
        for item in range(80):
            population.append(_row(index, stratum, companies[item % len(companies)]))
            index += 1
    result = select_worthiness_sample(population, protocol)
    assert result["employer_cap_effective"] == 9
    assert [item["to_cap"] for item in result["cap_relaxations"]] == [6, 7, 8, 9]
    assert max(result["employer_counts"].values()) == 9
    assert len(result["employer_counts"]) >= 15


def test_blind_review_hides_triage_cache_and_system_decision_fields():
    selection = select_worthiness_sample(_population(), load_worthiness_protocol())
    review = render_blind_review(_enriched_manifest(selection))
    assert "Would it be worth spending deeper AI reasoning" in review
    assert "SEMANTIC_PRIORITY" not in review
    assert "SEMANTIC_OPTIONAL" not in review
    assert "SEMANTIC_DEFER" not in review
    assert "cache" not in review.lower()
    assert "system recommendation" not in review.lower()
    assert "APPLY/DONT_APPLY decision" in review


def test_judgments_are_append_only_validated_and_supersession_safe(tmp_path):
    protocol = load_worthiness_protocol()
    manifest = _enriched_manifest(select_worthiness_sample(_population(), protocol), protocol)
    judgments = tmp_path / "judgments.jsonl"
    replacements = tmp_path / "replacements.jsonl"
    first = append_worthiness_judgment(
        manifest, judgments, replacements, "WORTH_DEEP_ASSESSMENT",
        review_number=1, reasons=["PLAUSIBLE_TARGET_ROLE"],
    )
    with pytest.raises(SemanticWorthinessError, match="current judgment exists"):
        append_worthiness_judgment(
            manifest, judgments, replacements, "NOT_WORTH_DEEP_ASSESSMENT",
            review_number=1,
        )
    second = append_worthiness_judgment(
        manifest, judgments, replacements, "NOT_WORTH_DEEP_ASSESSMENT",
        review_number=1, supersedes=first["record_id"],
    )
    assert len(load_jsonl(judgments)) == 2
    assert second["supersedes_record_id"] == first["record_id"]
    with pytest.raises(SemanticWorthinessError, match="invalid worthiness reasons"):
        append_worthiness_judgment(
            manifest, judgments, replacements, "WORTH_DEEP_ASSESSMENT",
            review_number=2, reasons=["NOT_CONTROLLED"],
        )


def test_unavailable_replacement_uses_frozen_same_stratum_reserve(tmp_path):
    protocol = load_worthiness_protocol()
    manifest = _enriched_manifest(select_worthiness_sample(_population(), protocol), protocol)
    replacements = tmp_path / "replacements.jsonl"
    judgments = tmp_path / "judgments.jsonl"
    original = manifest["sample"]["selected"][0]
    value = append_replacement(
        manifest, replacements, judgments, original["review_number"], "UNAVAILABLE",
    )
    effective = effective_selected_items(manifest, load_jsonl(replacements))
    replacement = next(item for item in effective if item["review_number"] == original["review_number"])
    assert value["stratum"] == original["stratum"] == replacement["stratum"]
    assert replacement["cluster_id"] != original["cluster_id"]
    assert replacement["cluster_id"] in {
        item["cluster_id"] for item in manifest["sample"]["reserves"][original["stratum"]]
    }


def test_metrics_and_directional_gates_are_deterministic(tmp_path):
    protocol = load_worthiness_protocol()
    manifest = _enriched_manifest(select_worthiness_sample(_population(), protocol), protocol)
    judgments = []
    for item in manifest["sample"]["selected"]:
        position = sum(
            other["review_number"] <= item["review_number"] and other["stratum"] == item["stratum"]
            for other in manifest["sample"]["selected"]
        )
        if item["stratum"] == "SEMANTIC_PRIORITY":
            label = "WORTH_DEEP_ASSESSMENT" if position <= 12 else "NOT_WORTH_DEEP_ASSESSMENT"
        elif item["stratum"] == "SEMANTIC_DEFER":
            label = "WORTH_DEEP_ASSESSMENT" if position <= 2 else "NOT_WORTH_DEEP_ASSESSMENT"
        else:
            label = "WORTH_DEEP_ASSESSMENT" if position <= 10 else "NOT_WORTH_DEEP_ASSESSMENT"
        judgments.append({
            "record_id": f"judgment-{item['review_number']}",
            "preparation_id": manifest["preparation_id"],
            "cluster_id": item["cluster_id"],
            "label": label,
            "supersedes_record_id": None,
        })
    metrics = calculate_worthiness_metrics(manifest, judgments, [], protocol)
    assert metrics["status"] == "COMPLETE"
    assert metrics["priority_precision"] == 0.6
    assert metrics["defer_safety"] == 0.9
    assert metrics["defer_worth_count"] == 2
    assert metrics["all_directional_gates_pass"] is True
    assert metrics["counterfactual_economics"]["PRIORITY_ONLY"]["current_population_projected_calls"] == 10


def test_prepare_is_read_only_zero_call_and_sanitizes_aggregate(tmp_path, monkeypatch):
    database = tmp_path / "state.sqlite3"
    database.write_bytes(b"immutable fixture state")
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    mtime = database.stat().st_mtime_ns
    population = _population()
    allocation = load_allocation_audit_config(
        ROOT / "experiments/semantic_compute_allocation_v1.yaml"
    )
    taxonomy = load_taxonomy(ROOT / "config/taxonomy.yaml")
    candidate = load_candidate_profile(ROOT / "config/candidate.yaml", taxonomy)
    fake_bundle = {
        "routed_population": population,
        "historical_exclusion": {"excluded_cluster_count": 26, "overlapping_member_count": 30},
        "config": allocation,
        "protocol": load_prospective_protocol(
            ROOT / "experiments/phase4_prospective_validation_v1.yaml"
        ),
        "context": {"profile": candidate},
    }
    monkeypatch.setattr(
        "opportunity_radar.semantic_worthiness_validation.build_presemantic_audit_population",
        lambda *args, **kwargs: fake_bundle,
    )
    monkeypatch.setattr(
        "opportunity_radar.semantic_worthiness_validation.observed_luna_cost",
        lambda *args, **kwargs: {"estimated_cost_per_cache_miss_usd": 0.002},
    )
    monkeypatch.setattr(
        "requests.post", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("external call")),
    )
    result = prepare_worthiness_validation(
        database, ROOT / "experiments/semantic_compute_worthiness_v1.yaml",
        tmp_path / "output", preparation_id="prep-read-only",
    )
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert database.stat().st_mtime_ns == mtime
    assert result["aggregate"]["integrity"] == {
        "database_unchanged": True,
        "external_semantic_calls": 0,
        "live_source_calls": 0,
        "prospective_batches_created": 0,
        "human_judgments_created": 0,
        "blind_review_hides_triage": True,
        "selection_is_cache_blind": True,
    }
    aggregate_text = json.dumps(result["aggregate"])
    for row in population:
        assert row["cluster_id"] not in aggregate_text
        assert row["title"] not in aggregate_text
        assert row["canonical_url"] not in aggregate_text
    assert result["aggregate"]["status"] == "PREPARED_AWAITING_HUMAN_REVIEW"


def test_private_worthiness_evidence_is_ignored_but_aggregate_is_trackable():
    for path in (
        "output/semantic_compute_worthiness/example/manifest.json",
        "output/semantic_compute_worthiness/example/blind_review.md",
        "data/semantic_compute_worthiness/judgments.jsonl",
    ):
        assert subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0
    assert subprocess.run(
        ["git", "check-ignore", "-q", "output/semantic_compute_worthiness/example/aggregate_summary.json"],
        cwd=ROOT,
    ).returncode == 1
    assert subprocess.run(
        ["git", "check-ignore", "-q", "output/semantic_compute_worthiness/example/aggregate_result.json"],
        cwd=ROOT,
    ).returncode == 1
