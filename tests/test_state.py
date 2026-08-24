from __future__ import annotations

from datetime import datetime, timezone

import pytest

from opportunity_radar.change_detection import compare_material, fingerprint, material
from opportunity_radar.models import JobLocation, JobReference, NormalizedJob, WorkMode
from opportunity_radar.state_models import DetailObservation, SourceOutcome
from opportunity_radar.state_repository import StateRepository
from opportunity_radar.state_runner import observe_source
from opportunity_radar.config import CompanyConfig


AT = datetime(2026, 8, 24, 10, tzinfo=timezone.utc)


def job(job_id="A", *, mode=WorkMode.HYBRID, description="Build <b>useful</b> things", locations=None):
    return NormalizedJob(
        "acme", "Acme", job_id, f"Role {job_id}",
        locations or [JobLocation("Prague, Czechia", "Prague", None, "Czechia")],
        mode, f"https://acme.example/{job_id}", description, None, None,
        "Full time", "Engineering", "fixture", AT,
    )


def ref(job_id):
    return JobReference("acme", job_id, f"https://acme.example/{job_id}")


def outcome(*ids, details=None, status="SUCCESS", inventory_complete=True, details_complete=True):
    references = [ref(value) for value in ids]
    detail_jobs = details if details is not None else [job(value) for value in ids]
    observed = [DetailObservation(ref(item.external_job_id), item) for item in detail_jobs]
    return SourceOutcome(
        "acme", "Acme", "fixture", status, AT, references, observed,
        inventory_complete, details_complete, len(references),
        len(references) - len(observed),
    )


def apply(repo, run_id, value):
    repo.create_run(run_id, AT.isoformat())
    repo.apply_outcome(run_id, value)
    repo.finish_run(run_id, AT.isoformat(), "COMPLETED")


def event_types(repo):
    return [row["event_type"] for row in repo.rows("events")]


def states(repo):
    return {row["external_job_id"]: row["lifecycle_state"] for row in repo.rows("job_instances")}


def test_new_unchanged_changed_closed_and_reopened(tmp_path):
    repo = StateRepository(tmp_path / "state.db")
    apply(repo, "r1", outcome("A", "B"))
    assert event_types(repo) == ["NEW", "NEW"]
    apply(repo, "r2", outcome("A", "B"))
    assert event_types(repo) == ["NEW", "NEW"]
    changed = job("A", mode=WorkMode.REMOTE)
    apply(repo, "r3", outcome("A", "C", details=[changed, job("C")]))
    assert states(repo) == {"A": "ACTIVE", "B": "CLOSED", "C": "ACTIVE"}
    assert "WORK_MODE_CHANGED" in event_types(repo)
    assert "CLOSED" in event_types(repo)
    apply(repo, "r4", outcome("A", "B", "C"))
    assert states(repo)["B"] == "ACTIVE"
    assert "REOPENED" in event_types(repo)


def test_confirmed_zero_closes_all_but_unvalidated_empty_does_not(tmp_path):
    repo = StateRepository(tmp_path / "state.db")
    apply(repo, "r1", outcome("A", "B"))
    failed = outcome(status="EXTRACTION_ERROR", inventory_complete=False, details_complete=False)
    apply(repo, "r2", failed)
    assert set(states(repo).values()) == {"ACTIVE"}
    apply(repo, "r3", outcome())
    assert set(states(repo).values()) == {"CLOSED"}


def test_present_known_job_with_failed_detail_remains_active_and_keeps_snapshot(tmp_path):
    repo = StateRepository(tmp_path / "state.db")
    apply(repo, "r1", outcome("A"))
    before = repo.rows("job_instances")[0]
    apply(repo, "r2", outcome("A", details=[], details_complete=False))
    after = repo.rows("job_instances")[0]
    assert after["lifecycle_state"] == "ACTIVE"
    assert after["current_fingerprint"] == before["current_fingerprint"]
    assert len(repo.rows("job_observations")) == 1


def test_sampled_details_do_not_overwrite_unsampled_jobs(tmp_path):
    repo = StateRepository(tmp_path / "state.db")
    apply(repo, "r1", outcome("A", "B"))
    old = {row["external_job_id"]: row["current_fingerprint"] for row in repo.rows("job_instances")}
    sampled = outcome("A", "B", details=[job("A", description="Changed")], details_complete=False)
    apply(repo, "r2", sampled)
    new = {row["external_job_id"]: row["current_fingerprint"] for row in repo.rows("job_instances")}
    assert new["A"] != old["A"]
    assert new["B"] == old["B"]
    assert states(repo)["B"] == "ACTIVE"


def test_transaction_rollback_preserves_previous_state(tmp_path, monkeypatch):
    repo = StateRepository(tmp_path / "state.db")
    apply(repo, "r1", outcome("A"))
    repo.create_run("r2", AT.isoformat())
    monkeypatch.setattr(repo, "_event", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        repo.apply_outcome("r2", outcome("B"))
    assert states(repo) == {"A": "ACTIVE"}
    assert len(repo.rows("source_observations")) == 1


def test_repeated_processing_and_repeated_closed_observation_are_idempotent(tmp_path):
    repo = StateRepository(tmp_path / "state.db")
    repo.create_run("r1", AT.isoformat())
    repo.apply_outcome("r1", outcome("A"))
    repo.apply_outcome("r1", outcome("A"))
    assert len(repo.rows("job_observations")) == 1
    assert event_types(repo) == ["NEW"]
    apply(repo, "r2", outcome())
    apply(repo, "r3", outcome())
    assert event_types(repo).count("CLOSED") == 1


def test_formatting_and_location_order_do_not_change_fingerprint():
    first = job(description="Build&nbsp; useful\nthings", locations=[JobLocation("Prague"), JobLocation("Brno")])
    second = job(description="<p>Build useful things</p>", locations=[JobLocation("Brno"), JobLocation("Prague")])
    assert fingerprint(first) == fingerprint(second)
    assert compare_material(material(first), material(second)) == []


def test_url_fallback_is_company_scoped_and_not_merged_with_later_external_id(tmp_path):
    repo = StateRepository(tmp_path / "state.db")
    url_ref = JobReference("acme", None, "https://acme.example/shared")
    first_job = job(None)
    first = SourceOutcome("acme", "Acme", "fixture", "SUCCESS", AT, [url_ref], [DetailObservation(url_ref, first_job)], True, True, 1)
    apply(repo, "r1", first)
    external_ref = JobReference("acme", "X", "https://acme.example/shared")
    second_job = job("X")
    second = SourceOutcome("acme", "Acme", "fixture", "SUCCESS", AT, [external_ref], [DetailObservation(external_ref, second_job)], True, True, 1)
    apply(repo, "r2", second)
    assert len(repo.rows("job_instances")) == 2


def test_adapter_empty_without_confirmed_zero_is_incomplete(monkeypatch):
    class EmptyAdapter:
        def list_jobs(self, config):
            return []

    monkeypatch.setattr("opportunity_radar.state_runner.AdapterRegistry.create", lambda config: EmptyAdapter())
    result = observe_source(CompanyConfig("acme", "Acme", "fixture"))
    assert result.status == "EXTRACTION_ERROR"
    assert result.inventory_complete is False
