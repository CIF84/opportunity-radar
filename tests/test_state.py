from __future__ import annotations

from datetime import datetime, timezone

import pytest

from opportunity_radar.change_detection import compare_material, fingerprint, material
from opportunity_radar.models import JobLocation, JobReference, ListingFacts, NormalizedJob, WorkMode
from opportunity_radar.state_models import DetailObservation, SourceOutcome
from opportunity_radar.state_repository import StateRepository
from opportunity_radar.state_runner import observe_source, run_stateful
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


def scoped_ref(job_id, location, *, title=None, source_updated_at=None):
    return JobReference(
        "acme", job_id, f"https://acme.example/{job_id}",
        listing_facts=ListingFacts(
            title=title, locations=(JobLocation(location),),
            source_updated_at=source_updated_at,
        ),
    )


def outcome(*ids, details=None, status="SUCCESS", inventory_complete=True, details_complete=True):
    references = [ref(value) for value in ids]
    detail_jobs = details if details is not None else [job(value) for value in ids]
    observed = [DetailObservation(ref(item.external_job_id), item) for item in detail_jobs]
    return SourceOutcome(
        "acme", "Acme", "fixture", status, AT, references, observed,
        inventory_complete, details_complete, len(references),
        len(references) - len(observed), selected_for_detail_count=len(references),
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


def test_state_refresh_progress_and_max_jobs_diagnostics(tmp_path, monkeypatch, capsys):
    class FixtureAdapter:
        def list_jobs(self, config):
            return [ref("A"), ref("B"), ref("C")]

        def fetch_job(self, reference):
            return job(reference.external_job_id)

    monkeypatch.setattr(
        "opportunity_radar.state_runner.AdapterRegistry.create",
        lambda config: FixtureAdapter(),
    )
    repo = StateRepository(tmp_path / "state.db")
    _, outcomes, status = run_stateful(
        [CompanyConfig("acme", "Acme", "fixture")], repo, max_jobs=2, run_id="progress",
    )
    output = capsys.readouterr().out
    assert "[1/1] START company=acme adapter=fixture" in output
    assert "[1/1] INVENTORY company=acme jobs=3 elapsed=" in output
    assert "[1/1] DETAILS company=acme 2/2 elapsed=" in output
    assert "[1/1] SUCCESS company=acme" in output
    assert "inventory=3" in output
    assert "details_fetched=2" in output
    assert "detail_failures=0" in output
    assert "employers=1" in output
    assert "jobs_discovered=3" in output
    assert "details_fetched=2" in output
    assert status == "PARTIAL"
    assert outcomes[0].inventory_complete is True
    assert outcomes[0].details_complete is False


def test_state_refresh_reports_list_failure_and_isolates_next_employer(tmp_path, monkeypatch, capsys):
    class Adapter:
        def __init__(self, fail):
            self.fail = fail

        def list_jobs(self, config):
            if self.fail:
                raise RuntimeError("fixture list failure")
            return [JobReference(config.company_id, "A", f"https://{config.company_id}.example/A")]

        def fetch_job(self, reference):
            value = job("A")
            return NormalizedJob(
                reference.company_id, reference.company_id, value.external_job_id, value.title,
                value.locations, value.work_mode, reference.canonical_url, value.description,
                value.date_posted, value.valid_through, value.employment_type, value.department,
                value.source, value.retrieved_at,
            )

    monkeypatch.setattr(
        "opportunity_radar.state_runner.AdapterRegistry.create",
        lambda config: Adapter(config.company_id == "broken"),
    )
    configs = [CompanyConfig("broken", "Broken", "fixture"), CompanyConfig("working", "Working", "fixture")]
    _, outcomes, status = run_stateful(configs, StateRepository(tmp_path / "state.db"), run_id="isolated")
    output = capsys.readouterr().out
    assert "[1/2] FAIL company=broken" in output
    assert "stage=list" in output
    assert "error_type=RuntimeError" in output
    assert "[2/2] SUCCESS company=working" in output
    assert [item.status for item in outcomes] == ["EXTRACTION_ERROR", "SUCCESS"]
    assert status == "PARTIAL"


def test_scope_selection_preserves_complete_inventory_and_skips_only_details(monkeypatch):
    class Adapter:
        calls = []

        def list_jobs(self, config):
            return [scoped_ref("CZ", "Prague, Czechia"), scoped_ref("US", "New York, United States")]

        def fetch_job(self, reference):
            self.calls.append(reference.external_job_id)
            return job(reference.external_job_id)

    adapter = Adapter()
    monkeypatch.setattr("opportunity_radar.state_runner.AdapterRegistry.create", lambda config: adapter)
    result = observe_source(CompanyConfig("acme", "Acme", "fixture"))
    assert [reference.external_job_id for reference in result.references] == ["CZ", "US"]
    assert adapter.calls == ["CZ"]
    assert result.inventory_count == 2
    assert result.selected_for_detail_count == 1
    assert result.intentionally_skipped_count == 1
    assert result.detail_failure_count == 0
    assert result.selected_details_complete is True


def test_new_skipped_job_is_not_created_but_existing_skipped_job_stays_active(tmp_path):
    repo = StateRepository(tmp_path / "state.db")
    apply(repo, "r1", outcome("KNOWN"))
    skipped = SourceOutcome(
        "acme", "Acme", "fixture", "SUCCESS", AT,
        [scoped_ref("KNOWN", "New York, United States"), scoped_ref("NEW", "Berlin, Germany")],
        [], True, True, 2, 0, selected_for_detail_count=0, intentionally_skipped_count=2,
    )
    apply(repo, "r2", skipped)
    assert states(repo) == {"KNOWN": "ACTIVE"}
    assert len(repo.rows("job_instances")) == 1


def test_max_jobs_applies_after_scope_selection_and_marks_selected_details_incomplete(monkeypatch):
    class Adapter:
        calls = []

        def list_jobs(self, config):
            return [
                scoped_ref("OUT", "Berlin, Germany"),
                scoped_ref("A", "Prague, Czechia"),
                scoped_ref("B", "Brno, Czechia"),
            ]

        def fetch_job(self, reference):
            self.calls.append(reference.external_job_id)
            return job(reference.external_job_id)

    adapter = Adapter()
    monkeypatch.setattr("opportunity_radar.state_runner.AdapterRegistry.create", lambda config: adapter)
    result = observe_source(CompanyConfig("acme", "Acme", "fixture"), max_jobs=1)
    assert adapter.calls == ["A"]
    assert result.inventory_complete is True
    assert result.selected_for_detail_count == 2
    assert result.intentionally_skipped_count == 1
    assert result.selected_details_complete is False


def test_selected_detail_failure_is_not_an_intentional_skip(monkeypatch):
    class Adapter:
        def list_jobs(self, config):
            return [scoped_ref("A", "Prague, Czechia"), scoped_ref("OUT", "Berlin, Germany")]

        def fetch_job(self, reference):
            raise RuntimeError("detail unavailable")

    monkeypatch.setattr("opportunity_radar.state_runner.AdapterRegistry.create", lambda config: Adapter())
    result = observe_source(CompanyConfig("acme", "Acme", "fixture"))
    assert result.inventory_complete is True
    assert result.selected_for_detail_count == 1
    assert result.intentionally_skipped_count == 1
    assert result.detail_failure_count == 1
    assert result.selected_details_complete is False


class ReuseAdapter:
    def __init__(self, references):
        self.references = references
        self.calls = []

    def list_jobs(self, config):
        return list(self.references)

    def fetch_job(self, reference):
        self.calls.append(reference.external_job_id)
        return job(reference.external_job_id)


def _run_reuse(repo, adapter, monkeypatch, run_id, *, refresh_hours=168):
    monkeypatch.setattr("opportunity_radar.state_runner.AdapterRegistry.create", lambda config: adapter)
    return run_stateful(
        [CompanyConfig("acme", "Acme", "fixture")], repo, run_id=run_id,
        detail_refresh_hours=refresh_hours,
    )[1][0]


def test_first_observation_fetches_and_unchanged_next_run_reuses(tmp_path, monkeypatch):
    repo = StateRepository(tmp_path / "state.db")
    reference = scoped_ref("A", "Prague, Czechia", title="Role")
    first_adapter = ReuseAdapter([reference])
    first = _run_reuse(repo, first_adapter, monkeypatch, "reuse-1")
    instance_before = dict(repo.rows("job_instances")[0])
    observations_before = len(repo.rows("job_observations"))

    second_adapter = ReuseAdapter([reference])
    second = _run_reuse(repo, second_adapter, monkeypatch, "reuse-2")
    instance_after = dict(repo.rows("job_instances")[0])

    assert first_adapter.calls == ["A"] and first.details_to_fetch_count == 1
    assert second_adapter.calls == []
    assert second.reused_detail_count == 1 and second.details_to_fetch_count == 0
    assert len(repo.rows("job_observations")) == observations_before
    assert instance_after["current_fingerprint"] == instance_before["current_fingerprint"]
    assert instance_after["latest_observation_id"] == instance_before["latest_observation_id"]
    assert event_types(repo) == ["NEW"]


def test_listing_fingerprint_and_source_updated_changes_trigger_fetch(tmp_path, monkeypatch):
    repo = StateRepository(tmp_path / "state.db")
    original = scoped_ref("A", "Prague, Czechia", title="Original")
    _run_reuse(repo, ReuseAdapter([original]), monkeypatch, "change-1")

    listing_changed = ReuseAdapter([scoped_ref("A", "Prague, Czechia", title="Changed")])
    listing_outcome = _run_reuse(repo, listing_changed, monkeypatch, "change-2")
    assert listing_changed.calls == ["A"] and listing_outcome.details_to_fetch_count == 1

    updated = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    source_changed = ReuseAdapter([
        scoped_ref("A", "Prague, Czechia", title="Changed", source_updated_at=updated),
    ])
    source_outcome = _run_reuse(repo, source_changed, monkeypatch, "change-3")
    assert source_changed.calls == ["A"] and source_outcome.details_to_fetch_count == 1


def test_periodic_refresh_zero_interval_forces_fetch(tmp_path, monkeypatch):
    repo = StateRepository(tmp_path / "state.db")
    reference = scoped_ref("A", "Prague, Czechia")
    _run_reuse(repo, ReuseAdapter([reference]), monkeypatch, "periodic-1")
    adapter = ReuseAdapter([reference])
    outcome = _run_reuse(repo, adapter, monkeypatch, "periodic-2", refresh_hours=0)
    assert adapter.calls == ["A"]
    assert outcome.reused_detail_count == 0 and outcome.details_to_fetch_count == 1


def test_previously_skipped_job_fetches_when_it_becomes_selected(tmp_path, monkeypatch):
    repo = StateRepository(tmp_path / "state.db")
    skipped_adapter = ReuseAdapter([scoped_ref("A", "Berlin, Germany")])
    skipped = _run_reuse(repo, skipped_adapter, monkeypatch, "scope-change-1")
    assert skipped_adapter.calls == [] and skipped.intentionally_skipped_count == 1
    assert repo.rows("job_instances") == []

    selected_adapter = ReuseAdapter([scoped_ref("A", "Prague, Czechia")])
    selected = _run_reuse(repo, selected_adapter, monkeypatch, "scope-change-2")
    assert selected_adapter.calls == ["A"] and selected.details_to_fetch_count == 1
    assert states(repo) == {"A": "ACTIVE"}


def test_reuse_keeps_presence_inventory_driven_and_closes_absent_job(tmp_path, monkeypatch):
    repo = StateRepository(tmp_path / "state.db")
    both = [scoped_ref("A", "Prague, Czechia"), scoped_ref("B", "Prague, Czechia")]
    _run_reuse(repo, ReuseAdapter(both), monkeypatch, "closure-reuse-1")
    only_a = ReuseAdapter([both[0]])
    outcome = _run_reuse(repo, only_a, monkeypatch, "closure-reuse-2")
    assert only_a.calls == [] and outcome.reused_detail_count == 1
    assert states(repo) == {"A": "ACTIVE", "B": "CLOSED"}
