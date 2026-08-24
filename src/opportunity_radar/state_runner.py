from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from opportunity_radar.adapters.base import (
    ConfirmedEmptyInventoryError, CountMismatchError, SchemaMismatchError,
    SourceRequestError, UnvalidatedEmptyInventoryError,
)
from opportunity_radar.config import CompanyConfig, ConfigurationError, load_companies
from opportunity_radar.models import utc_now
from opportunity_radar.registry import AdapterRegistry
from opportunity_radar.state_models import DetailObservation, SourceOutcome
from opportunity_radar.state_repository import StateRepository


def observe_source(config: CompanyConfig, max_jobs: int | None = None) -> SourceOutcome:
    observed_at = utc_now()
    try:
        adapter = AdapterRegistry.create(config)
        try:
            references = adapter.list_jobs(config)
        except ConfirmedEmptyInventoryError:
            return SourceOutcome(
                config.company_id, config.company_name, config.adapter, "SUCCESS",
                observed_at, inventory_complete=True, details_complete=True,
                expected_count=0,
            )
        if not references:
            raise UnvalidatedEmptyInventoryError(
                f"{config.company_id}: adapter returned no identities without confirmed-zero evidence"
            )
        selected = references[:max_jobs] if max_jobs is not None else references
        details = []
        failures = []
        for reference in selected:
            try:
                details.append(DetailObservation(reference, adapter.fetch_job(reference)))
            except Exception as exc:
                failures.append(f"{reference.canonical_url}: {type(exc).__name__}: {exc}")
        sampled = len(selected) < len(references)
        return SourceOutcome(
            config.company_id, config.company_name, config.adapter, "SUCCESS",
            observed_at, references, details, inventory_complete=True,
            details_complete=not sampled and not failures,
            expected_count=len(references), detail_failure_count=len(failures),
            error_type="DetailError" if failures else None,
            error_message="; ".join(failures[:3]) or None,
        )
    except Exception as exc:
        if isinstance(exc, CountMismatchError):
            status = "COUNT_MISMATCH"
        elif isinstance(exc, SchemaMismatchError):
            status = "SCHEMA_MISMATCH"
        elif isinstance(exc, SourceRequestError):
            status = "REQUEST_ERROR"
        elif isinstance(exc, UnvalidatedEmptyInventoryError):
            status = "EXTRACTION_ERROR"
        elif isinstance(exc, ConfigurationError):
            status = "CONFIG_ERROR"
        else:
            status = "EXTRACTION_ERROR"
        return SourceOutcome(
            config.company_id, config.company_name, config.adapter, status,
            observed_at, inventory_complete=False, details_complete=False,
            error_type=type(exc).__name__, error_message=str(exc),
        )


def run_stateful(
    configs: list[CompanyConfig], repository: StateRepository,
    max_jobs: int | None = None, run_id: str | None = None,
) -> tuple[str, list[SourceOutcome], str]:
    run_id = run_id or str(uuid.uuid4())
    started = utc_now()
    repository.create_run(run_id, started.isoformat())
    outcomes = []
    for config in configs:
        outcome = observe_source(config, max_jobs)
        try:
            repository.apply_outcome(run_id, outcome)
        except Exception as exc:
            outcome = replace(
                outcome, status="INTERNAL_ERROR", inventory_complete=False,
                details_complete=False, error_type=type(exc).__name__,
                error_message=str(exc),
            )
            repository.record_failure(run_id, outcome)
        outcomes.append(outcome)
    successful = [item for item in outcomes if item.status == "SUCCESS"]
    fully_complete = [
        item for item in successful if item.inventory_complete and item.details_complete
    ]
    if len(fully_complete) == len(outcomes):
        status = "COMPLETED"
    elif successful:
        status = "PARTIAL"
    else:
        status = "FAILED"
    repository.finish_run(run_id, utc_now().isoformat(), status)
    return run_id, outcomes, status


def write_state_report(repository: StateRepository, run_id: str, outcomes, status, path: str | Path):
    events = [row for row in repository.rows("events") if row["run_id"] == run_id]
    active = sum(row["lifecycle_state"] == "ACTIVE" for row in repository.rows("job_instances"))
    closed = sum(row["lifecycle_state"] == "CLOSED" for row in repository.rows("job_instances"))
    lines = [
        "OPPORTUNITY RADAR — PHASE 2 STATE RUN", "", f"Run: {run_id}",
        f"Status: {status}", f"Sources: {len(outcomes)}", f"Active jobs: {active}",
        f"Closed jobs: {closed}", f"Events in run: {len(events)}", "",
    ]
    for outcome in outcomes:
        lines.append(
            f"{outcome.company_name}: {outcome.status}, inventory_complete={outcome.inventory_complete}, "
            f"details_complete={outcome.details_complete}, observed={outcome.observed_count}, "
            f"details={outcome.detail_success_count}/{outcome.observed_count}"
        )
        if outcome.error_message:
            lines.append(f"  {outcome.error_type}: {outcome.error_message}")
    lines.extend(["", "EVENTS"])
    lines.extend(
        f"{row['event_type']} job_instance_id={row['job_instance_id']}" for row in events
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 2 persistent state observation")
    parser.add_argument("--config", default="config/companies.yaml")
    parser.add_argument("--database", default="output/opportunity_radar.sqlite3")
    parser.add_argument("--report", default="output/state_change_report.txt")
    parser.add_argument("--max-jobs", type=int)
    parser.add_argument("--company", action="append", default=[])
    args = parser.parse_args()
    configs = load_companies(args.config)
    if args.company:
        configs = [item for item in configs if item.company_id in args.company]
    repository = StateRepository(args.database)
    run_id, outcomes, status = run_stateful(configs, repository, args.max_jobs)
    write_state_report(repository, run_id, outcomes, status, args.report)
    print(json.dumps({"run_id": run_id, "status": status}, indent=2))
    return 0 if status in {"COMPLETED", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
