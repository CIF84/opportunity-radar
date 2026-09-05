from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest
import yaml

from opportunity_radar.live_validation import (
    DISAGREEMENT_CATEGORIES,
    append_judgment,
    build_preflight,
    calculate_metrics,
    current_judgments,
    generate_report,
    load_judgments,
    prepare_batch,
    resolve_batch_job,
    run_luna_assessment,
    select_validation_sample,
)
from opportunity_radar.experimental_semantic import CallUsage, ModelResponse
from opportunity_radar.models import JobLocation, JobReference, NormalizedJob, WorkMode
from opportunity_radar.phase3_benchmark import load_active_semantic_jobs
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_pipeline import assess_opportunity
from opportunity_radar.phase3_repository import Phase3Repository
from opportunity_radar.semantic import DeterministicSemanticAssessor
from opportunity_radar.state_models import DetailObservation, SourceOutcome
from opportunity_radar.state_repository import SCHEMA_VERSION, StateRepository


AT = datetime(2026, 8, 26, tzinfo=timezone.utc)


class LunaFixtureAssessor(DeterministicSemanticAssessor):
    assessor_id = "external-structured"
    assessor_version = "1:gpt-5.6-luna"

    def assess(self, job, candidate, features):
        result = super().assess(job, candidate, features)
        return replace(
            result,
            assessor_id=self.assessor_id,
            assessor_version=self.assessor_version,
        )


def _job(external_id: str, location: JobLocation, description: str | None = None) -> NormalizedJob:
    return NormalizedJob(
        "acme", "Acme", external_id, f"Role {external_id}", [location], WorkMode.HYBRID,
        f"https://example.test/jobs/{external_id}",
        description or "Lead product analytics and AI strategy with senior stakeholders.",
        None, None, "Full time", "Product", "fixture", AT,
    )


def _seed(tmp_path, count: int = 6):
    database = tmp_path / "state.sqlite3"
    state = StateRepository(database)
    jobs = [
        _job(str(index), JobLocation("Prague, Czechia", "Prague", None, "Czechia"))
        for index in range(count)
    ]
    jobs.append(_job("us", JobLocation("New York, United States", "New York", None, "United States")))
    refs = [JobReference(job.company_id, job.external_job_id, job.canonical_url) for job in jobs]
    state.create_run("run-1", AT.isoformat())
    state.apply_outcome("run-1", SourceOutcome(
        "acme", "Acme", "fixture", "SUCCESS", AT, refs,
        [DetailObservation(ref, job) for ref, job in zip(refs, jobs)], True, True, len(refs),
    ))
    state.finish_run("run-1", AT.isoformat(), "COMPLETED")
    with state.connect() as connection:
        connection.execute(
            """INSERT INTO job_instances(company_id,external_job_id,canonical_url,first_seen_at,last_seen_at,lifecycle_state)
               VALUES ('acme','missing','https://example.test/jobs/missing',?,?,'ACTIVE')""",
            (AT.isoformat(), AT.isoformat()),
        )

    candidate_raw = yaml.safe_load(open("config/candidate.yaml", encoding="utf-8"))
    candidate_raw["hard_constraints"]["mandatory_location_exclusions"] = ["United States"]
    candidate_path = tmp_path / "candidate.yaml"
    candidate_path.write_text(yaml.safe_dump(candidate_raw, sort_keys=False), encoding="utf-8")
    return state, database, candidate_path


def _persist_luna(state: StateRepository, candidate_path, limit: int | None = None):
    taxonomy = load_taxonomy("config/taxonomy.yaml")
    profile = load_candidate_profile(candidate_path, taxonomy)
    assessor = LunaFixtureAssessor(taxonomy)
    rows = load_active_semantic_jobs(state)
    saved = 0
    for job_id, observation_id, content_fp, job in rows:
        if job.locations and job.locations[0].get("country") == "United States":
            continue
        assess_opportunity(
            job, profile, taxonomy, assessor, repository=Phase3Repository(state),
            job_instance_id=job_id, job_observation_id=observation_id,
            content_fingerprint=content_fp,
        )
        saved += 1
        if limit is not None and saved >= limit:
            break


def _preflight(database, candidate_path):
    return build_preflight(
        database, candidate_path=candidate_path,
        roi_results_path="output/semantic_roi_experiment.json",
    )


def test_preflight_is_read_only_and_classifies_cache_and_missing_detail(tmp_path, monkeypatch):
    state, database, candidate_path = _seed(tmp_path, 3)
    _persist_luna(state, candidate_path, limit=1)
    before = database.stat().st_mtime_ns

    def forbidden(*args, **kwargs):
        raise AssertionError("preflight attempted external transport")

    monkeypatch.setattr("requests.post", forbidden)
    result = _preflight(database, candidate_path)
    assert result["read_only"] is True
    assert result["configured_employers"] == 18
    assert result["active_jobs"] == 5
    assert result["active_jobs_with_usable_semantic_details"] == 4
    assert result["unassessable_detail_missing_count"] == 1
    assert result["unassessable_detail_missing"][0]["classification"] == "UNASSESSABLE_DETAIL_MISSING"
    assert result["eligibility"] == {"ELIGIBLE": 3, "UNCERTAIN": 0, "INELIGIBLE": 1}
    assert result["market_status"] == {
        "IN_SCOPE": 3, "UNCERTAIN": 0, "OUT_OF_SCOPE": 1,
    }
    assert result["jobs_eligible_for_semantic_processing"] == 3
    assert result["compatible_luna_cache_hits"] == 1
    assert result["out_of_scope_existing_cache_hits"] == 0
    assert result["luna_cache_misses"] == 2
    assert result["expected_external_calls"] == 2
    assert database.stat().st_mtime_ns == before
    assert state.rows("semantic_assessments")
    assert SCHEMA_VERSION == 3


def test_uncertain_is_counted_as_assessable_and_ineligible_is_not_a_cache_miss(tmp_path):
    _, database, candidate_path = _seed(tmp_path, 1)
    with StateRepository(database).connect() as connection:
        row = connection.execute("SELECT normalized_snapshot FROM job_observations jo JOIN job_instances ji ON ji.latest_observation_id=jo.job_observation_id WHERE ji.external_job_id='0'").fetchone()
        snapshot = json.loads(row[0]); snapshot["locations"] = []
        connection.execute("UPDATE job_observations SET normalized_snapshot=? WHERE job_observation_id=(SELECT latest_observation_id FROM job_instances WHERE external_job_id='0')", (json.dumps(snapshot),))
    result = _preflight(database, candidate_path)
    assert result["eligibility"]["UNCERTAIN"] == 1
    assert result["eligibility"]["INELIGIBLE"] == 1
    assert result["market_status"] == {
        "IN_SCOPE": 0, "UNCERTAIN": 1, "OUT_OF_SCOPE": 1,
    }
    assert result["jobs_eligible_for_semantic_processing"] == 1
    assert result["luna_cache_misses"] == 1


def test_explicit_assessment_processes_uncertain_but_not_ineligible(tmp_path, monkeypatch):
    state, database, candidate_path = _seed(tmp_path, 1)
    with state.connect() as connection:
        row = connection.execute("SELECT job_observation_id,normalized_snapshot FROM job_observations jo JOIN job_instances ji ON ji.latest_observation_id=jo.job_observation_id WHERE ji.external_job_id='0'").fetchone()
        snapshot = json.loads(row["normalized_snapshot"]); snapshot["locations"] = []
        connection.execute("UPDATE job_observations SET normalized_snapshot=? WHERE job_observation_id=?", (json.dumps(snapshot), row["job_observation_id"]))

    class OfflineTransport:
        calls = 0

        def complete(self, model, instructions, payload, schema):
            self.calls += 1
            dimensions = {
                key: {"score": 3, "confidence": "MEDIUM", "reason": "Synthetic offline response", "job_evidence": [], "candidate_evidence": []}
                for key in schema["properties"]["dimensions"]["properties"]
            }
            usage = CallUsage(model.model, 100, 0, 50, 10, 0.01, True, 0, 0.00008)
            return ModelResponse({"dimensions": dimensions, "strengths": [], "gaps": [], "risks": []}, usage)

    transport = OfflineTransport()
    monkeypatch.setattr("opportunity_radar.live_validation.OpenAIResponsesTransport", lambda *args, **kwargs: transport)
    result = run_luna_assessment(
        database, tmp_path / "validation", candidate_path=candidate_path,
        run_id="offline-explicit",
    )
    assert result["summary"]["jobs_processed"] == 1
    assert result["summary"]["external_calls"] == 1
    assert result["jobs"][0]["eligibility"] == "UNCERTAIN"
    assert result["jobs"][0]["market_status"] == "UNCERTAIN"
    assert result["jobs"][0]["recommendation"] == "REVIEW"
    assert result["jobs"][0]["routing"]["cap_applied"] is False
    assert transport.calls == 1
    assert len(state.rows("semantic_assessments")) == 1


def _pool(size: int):
    return [
        {"job_instance_id": index, "score": 10 - index / 10, "semantic": {}, "recommendation": "APPLY"}
        for index in range(size)
    ]


@pytest.mark.parametrize("size", [2, 7, 30, 42])
def test_sampling_is_deterministic_unique_and_preserves_small_pool_strata(size):
    first = select_validation_sample(_pool(size), "fixed-seed")
    second = select_validation_sample(_pool(size), "fixed-seed")
    assert first == second
    assert len(first) == min(size, 30)
    assert len({item["job_instance_id"] for item in first}) == len(first)
    if size >= 3:
        assert {item["stratum"] for item in first} == {"TOP_RANKED", "MARGINAL_BELOW_CUTOFF", "LOW_CONTROL"}


def test_prepare_writes_immutable_manifest_and_report_without_model_call(tmp_path, monkeypatch):
    state, database, candidate_path = _seed(tmp_path, 6)
    _persist_luna(state, candidate_path)
    monkeypatch.setattr("requests.post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("model called")))
    output = tmp_path / "validation"
    batch = prepare_batch(database, output, candidate_path=candidate_path, batch_id="fixed", seed="seed")
    assert (output / "fixed" / "batch.json").exists()
    assert (output / "fixed" / "review.md").exists()
    saved = json.loads((output / "fixed" / "batch.json").read_text())
    assert isinstance(saved["sampling"]["strata"], dict)
    assert saved["clustering"]["clustering_method_version"] == "phase4-high-confidence-cluster-v1"
    assert saved["clustering"]["preferred_variant_policy_version"] == "phase4-preferred-variant-v1"
    assert saved["clustering"]["normal_shortlist_cluster_count"] == batch["ranked_pool_size"]
    assert saved["clustering"]["clusters"]
    with pytest.raises(FileExistsError):
        prepare_batch(database, output, candidate_path=candidate_path, batch_id="fixed", seed="seed")
    assert len({item["job_instance_id"] for item in batch["selected_jobs"]}) == len(batch["selected_jobs"])


def test_judgments_are_append_only_validated_and_superseded(tmp_path):
    jobs = [
        {"review_number": 1, "job_instance_id": 10, "job_observation_id": 20,
         "content_fingerprint": "fp", "opportunity_assessment_id": 30}
    ]
    batch = {
        "validation_batch_id": "b1", "selected_jobs": jobs,
        "candidate": {"profile_id": "candidate", "version": 1, "scoring_preference_fingerprint": "weights"},
        "semantic": {"assessor_id": "external-structured", "model": "gpt-5.6-luna", "contract_version": "v1"},
    }
    path = tmp_path / "judgments.jsonl"
    first = append_judgment(batch, path, "1", "APPLY", True)
    with pytest.raises(ValueError):
        append_judgment(batch, path, "1", "REVIEW", False)
    with pytest.raises(ValueError):
        append_judgment(batch, path, "1", "REVIEW", False, categories=["NOT_CONTROLLED"])
    second = append_judgment(
        batch, path, "1", "REVIEW", False, expected_tier="HIGH",
        categories=[next(iter(DISAGREEMENT_CATEGORIES))], supersedes=first["judgment_id"],
    )
    records = load_judgments(path)
    assert len(records) == 2
    assert current_judgments(records, "b1")[("b1", 10)]["judgment_id"] == second["judgment_id"]


def test_legacy_identity_collision_is_rejected_and_explicit_identity_is_exact(tmp_path):
    jobs = [
        {"review_number": 6, "job_instance_id": 15, "job_observation_id": 60,
         "content_fingerprint": "six", "opportunity_assessment_id": 600},
        {"review_number": 15, "job_instance_id": 104, "job_observation_id": 150,
         "content_fingerprint": "fifteen", "opportunity_assessment_id": 1500},
    ]
    batch = {
        "validation_batch_id": "collision", "selected_jobs": jobs,
        "candidate": {"profile_id": "candidate", "version": 1, "scoring_preference_fingerprint": "weights"},
        "semantic": {"assessor_id": "external-structured", "model": "model", "contract_version": "v1"},
    }
    with pytest.raises(ValueError, match="ambiguous legacy positional id 15"):
        resolve_batch_job(batch, "15")
    assert resolve_batch_job(batch, review_number=15)["job_instance_id"] == 104
    assert resolve_batch_job(batch, job_instance_id=15)["review_number"] == 6

    judgment = append_judgment(
        batch, tmp_path / "judgments.jsonl", None, "DONT_APPLY", False,
        categories=["UNREPRESENTED_HUMAN_PREFERENCE"], review_number=15,
    )
    assert judgment["job_instance_id"] == 104


def test_metrics_and_report_use_only_reviewed_jobs_without_external_call(tmp_path, monkeypatch):
    selected = []
    for index, (stratum, recommendation, tier) in enumerate([
        ("TOP_RANKED", "APPLY", "TOP"),
        ("MARGINAL_BELOW_CUTOFF", "LOW_PRIORITY", "LOW"),
        ("LOW_CONTROL", "LOW_PRIORITY", "LOW"),
    ], 1):
        selected.append({
            "review_number": index, "job_instance_id": index, "job_observation_id": index,
            "content_fingerprint": f"fp{index}", "opportunity_assessment_id": index,
            "stratum": stratum, "recommendation": recommendation, "tier": tier,
        })
    batch = {
        "validation_batch_id": "metrics", "selected_jobs": selected,
        "candidate": {"profile_id": "candidate", "version": 1, "scoring_preference_fingerprint": "w"},
        "semantic": {"assessor_id": "external-structured", "model": "gpt-5.6-luna", "contract_version": "v1"},
        "preflight_snapshot": {"active_jobs": 3, "unassessable_detail_missing_count": 0, "eligibility": {"ELIGIBLE": 3, "UNCERTAIN": 0, "INELIGIBLE": 0}, "latest_run_event_counts": {"NEW": 3}, "source_failures_or_incomplete": []},
    }
    path = tmp_path / "judgments.jsonl"
    decisions = [("APPLY", True), ("APPLY", False), ("DONT_APPLY", True)]
    for index, (decision, agree) in enumerate(decisions, 1):
        append_judgment(batch, path, str(index), decision, agree, expected_tier=None if agree else "HIGH", categories=[] if agree else ["SCORING_WEIGHT_OR_CALIBRATION"])
    metrics = calculate_metrics(batch, load_judgments(path))
    assert metrics["reviewed"] == 3
    assert metrics["below_cutoff"]["human_apply_false_negative_count"] == 1
    assert metrics["below_cutoff"]["human_apply_false_negative_rate"] == 1.0
    assert metrics["verdict"] == "NOT_READY"
    monkeypatch.setattr("requests.post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("model called")))
    _, report = generate_report(batch, path, tmp_path)
    assert report.exists()
