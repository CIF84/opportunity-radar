from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from opportunity_radar.adapters.base import (
    ConfirmedEmptyInventoryError, CountMismatchError, SchemaMismatchError,
    SourceRequestError, UnvalidatedEmptyInventoryError,
)
from opportunity_radar.config import CompanyConfig, ConfigurationError, load_companies
from opportunity_radar.models import utc_now
from opportunity_radar.registry import AdapterRegistry
from opportunity_radar.scope_selection import (
    MarketScope, SelectionDecision, listing_facts_fingerprint, load_market_scope,
    select_for_detail,
)
from opportunity_radar.state_models import DetailObservation, SourceOutcome
from opportunity_radar.state_repository import StateRepository


LOCAL_DETAIL_ADAPTERS = frozenset({"json_feed", "phenom"})


@dataclass
class _ObservationProgress:
    index: int
    total: int
    employer_started: float
    stage: str = "list"

    @property
    def prefix(self) -> str:
        return f"[{self.index}/{self.total}]"

    def elapsed(self) -> float:
        return time.perf_counter() - self.employer_started


def _progress(message: str) -> None:
    print(message, flush=True)


def _identity(reference) -> tuple[str, str]:
    if reference.external_job_id is not None:
        return "external", str(reference.external_job_id)
    return "url", reference.canonical_url


def _source_updated_at(reference) -> str | None:
    return reference.listing_facts.to_dict()["source_updated_at"]


def should_fetch_detail(reference, evidence: dict | None, now: datetime, refresh_hours: float) -> tuple[bool, str]:
    """Pure, conservative detail-refresh decision."""
    if not evidence or not evidence.get("current_fingerprint") or not evidence.get("latest_observation_id"):
        return True, "NO_SUCCESSFUL_DETAIL"
    if not evidence.get("detail_listing_fingerprint") or not evidence.get("detail_refreshed_at"):
        return True, "NO_REUSE_EVIDENCE"
    current_updated = _source_updated_at(reference)
    if current_updated != evidence.get("detail_source_updated_at"):
        return True, "SOURCE_UPDATED_AT_CHANGED"
    current_listing = listing_facts_fingerprint(reference.listing_facts)
    if current_listing != evidence["detail_listing_fingerprint"]:
        return True, "LISTING_FACTS_CHANGED"
    refreshed_at = datetime.fromisoformat(evidence["detail_refreshed_at"])
    if refreshed_at.tzinfo is None:
        refreshed_at = refreshed_at.replace(tzinfo=timezone.utc)
    if now >= refreshed_at + timedelta(hours=refresh_hours):
        return True, "PERIODIC_REFRESH_DUE"
    return False, "UNCHANGED_REUSE"


def observe_source(
    config: CompanyConfig,
    max_jobs: int | None = None,
    progress: _ObservationProgress | None = None,
    detail_progress_interval: int = 25,
    slow_detail_seconds: float = 10.0,
    market_scope: MarketScope | None = None,
    repository: StateRepository | None = None,
    detail_refresh_hours: float = 168.0,
) -> SourceOutcome:
    observed_at = utc_now()
    market_scope = market_scope or load_market_scope("config/market_scope.yaml")
    try:
        adapter = AdapterRegistry.create(config)
        try:
            references = adapter.list_jobs(config)
        except ConfirmedEmptyInventoryError:
            if progress:
                _progress(
                    f"{progress.prefix} INVENTORY company={config.company_id} "
                    f"jobs=0 elapsed={progress.elapsed():.1f}s"
                )
            return SourceOutcome(
                config.company_id, config.company_name, config.adapter, "SUCCESS",
                observed_at, inventory_complete=True, selected_details_complete=True,
                expected_count=0,
            )
        if progress:
            _progress(
                f"{progress.prefix} INVENTORY company={config.company_id} "
                f"jobs={len(references)} elapsed={progress.elapsed():.1f}s"
            )
        if not references:
            raise UnvalidatedEmptyInventoryError(
                f"{config.company_id}: adapter returned no identities without confirmed-zero evidence"
            )
        selections = [(reference, select_for_detail(reference.listing_facts, market_scope)) for reference in references]
        selected_references = [reference for reference, selection in selections if selection.selected]
        intentionally_skipped_count = len(references) - len(selected_references)
        unknown_count = sum(
            selection.decision in {
                SelectionDecision.SELECT_GEOGRAPHY_UNKNOWN,
                SelectionDecision.SELECT_REMOTE_ELIGIBILITY_UNKNOWN,
            }
            for _, selection in selections
        )
        if progress:
            _progress(
                f"{progress.prefix} SCOPE company={config.company_id} "
                f"selected={len(selected_references)} skipped={intentionally_skipped_count} "
                f"unknown={unknown_count}"
            )
        selected = selected_references[:max_jobs] if max_jobs is not None else selected_references
        refresh_hours = float(config.options.get("detail_refresh_hours", detail_refresh_hours))
        if refresh_hours < 0:
            raise ConfigurationError("detail_refresh_hours must be non-negative")
        reuse_evidence = repository.detail_reuse_evidence(config.company_id) if repository else {}
        fetch_decisions = [
            (reference, *should_fetch_detail(
                reference, reuse_evidence.get(_identity(reference)), observed_at, refresh_hours,
            ))
            for reference in selected
        ]
        to_fetch = [reference for reference, fetch, _ in fetch_decisions if fetch]
        reused_count = len(selected) - len(to_fetch)
        if progress:
            _progress(
                f"{progress.prefix} DETAIL_PLAN company={config.company_id} "
                f"selected={len(selected_references)} reused={reused_count} "
                f"to_fetch={len(to_fetch)}"
            )
        details = []
        failures = []
        if progress:
            progress.stage = "detail"
        for detail_index, reference in enumerate(to_fetch, 1):
            detail_started = time.perf_counter()
            try:
                details.append(DetailObservation(reference, adapter.fetch_job(reference)))
            except Exception as exc:
                failures.append(f"{reference.canonical_url}: {type(exc).__name__}: {exc}")
            detail_elapsed = time.perf_counter() - detail_started
            if progress and detail_elapsed >= slow_detail_seconds:
                job_identity = reference.external_job_id or reference.canonical_url
                _progress(
                    f"{progress.prefix} SLOW_DETAIL company={config.company_id} "
                    f"job={detail_index}/{len(to_fetch)} job_id={job_identity} "
                    f"elapsed={detail_elapsed:.1f}s"
                )
            if progress and (
                detail_index == len(to_fetch) or detail_index % detail_progress_interval == 0
            ):
                _progress(
                    f"{progress.prefix} DETAILS company={config.company_id} "
                    f"{detail_index}/{len(to_fetch)} elapsed={progress.elapsed():.1f}s"
                )
        sampled = len(selected) < len(selected_references)
        return SourceOutcome(
            config.company_id, config.company_name, config.adapter, "SUCCESS",
            observed_at, references, details, inventory_complete=True,
            selected_details_complete=not sampled and not failures,
            expected_count=len(references),
            selected_for_detail_count=len(selected_references),
            intentionally_skipped_count=intentionally_skipped_count,
            network_detail_request_count=(
                0 if config.adapter in LOCAL_DETAIL_ADAPTERS else len(to_fetch)
            ),
            reused_detail_count=reused_count,
            details_to_fetch_count=len(to_fetch),
            detail_failure_count=len(failures),
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
            observed_at, inventory_complete=False, selected_details_complete=False,
            error_type=type(exc).__name__, error_message=str(exc),
        )


def run_stateful(
    configs: list[CompanyConfig], repository: StateRepository,
    max_jobs: int | None = None, run_id: str | None = None,
    market_scope_path: str | Path = "config/market_scope.yaml",
    detail_refresh_hours: float = 168.0,
) -> tuple[str, list[SourceOutcome], str]:
    run_id = run_id or str(uuid.uuid4())
    started = utc_now()
    run_started = time.perf_counter()
    repository.create_run(run_id, started.isoformat())
    market_scope = load_market_scope(market_scope_path)
    outcomes = []
    total = len(configs)
    for index, config in enumerate(configs, 1):
        employer_started = time.perf_counter()
        progress = _ObservationProgress(index, total, employer_started)
        _progress(
            f"{progress.prefix} START company={config.company_id} adapter={config.adapter}"
        )
        outcome = observe_source(
            config, max_jobs, progress, market_scope=market_scope,
            repository=repository, detail_refresh_hours=detail_refresh_hours,
        )
        try:
            repository.apply_outcome(run_id, outcome)
        except Exception as exc:
            outcome = replace(
                outcome, status="INTERNAL_ERROR", inventory_complete=False,
                selected_details_complete=False, error_type=type(exc).__name__,
                error_message=str(exc),
            )
            repository.record_failure(run_id, outcome)
            _progress(
                f"{progress.prefix} FAIL company={config.company_id}\n"
                f"    stage=persistence\n"
                f"    error_type={type(exc).__name__}\n"
                f"    elapsed={progress.elapsed():.1f}s"
            )
        else:
            if outcome.status == "SUCCESS":
                _progress(
                    f"{progress.prefix} SUCCESS company={config.company_id}\n"
                    f"    inventory={outcome.observed_count}\n"
                    f"    selected={outcome.selected_for_detail_count}\n"
                    f"    skipped={outcome.intentionally_skipped_count}\n"
                    f"    reused_details={outcome.reused_detail_count}\n"
                    f"    details_to_fetch={outcome.details_to_fetch_count}\n"
                    f"    details_fetched={outcome.detail_success_count}\n"
                    f"    detail_failures={outcome.detail_failure_count}\n"
                    f"    network_detail_requests={outcome.network_detail_request_count}\n"
                    f"    elapsed={progress.elapsed():.1f}s"
                )
            else:
                _progress(
                    f"{progress.prefix} FAIL company={config.company_id}\n"
                    f"    stage={progress.stage}\n"
                    f"    error_type={outcome.error_type or outcome.status}\n"
                    f"    elapsed={progress.elapsed():.1f}s"
                )
        outcomes.append(outcome)
    successful = [item for item in outcomes if item.status == "SUCCESS"]
    fully_complete = [
        item for item in successful if item.inventory_complete and item.selected_details_complete
    ]
    if len(fully_complete) == len(outcomes):
        status = "COMPLETED"
    elif successful:
        status = "PARTIAL"
    else:
        status = "FAILED"
    repository.finish_run(run_id, utc_now().isoformat(), status)
    _progress(
        "RUN SUMMARY\n"
        f"    employers={len(outcomes)}\n"
        f"    jobs_discovered={sum(item.observed_count for item in outcomes)}\n"
        f"    selected_for_detail={sum(item.selected_for_detail_count for item in outcomes)}\n"
        f"    intentionally_skipped={sum(item.intentionally_skipped_count for item in outcomes)}\n"
        f"    reused_details={sum(item.reused_detail_count for item in outcomes)}\n"
        f"    details_to_fetch={sum(item.details_to_fetch_count for item in outcomes)}\n"
        f"    details_fetched={sum(item.detail_success_count for item in outcomes)}\n"
        f"    detail_failures={sum(item.detail_failure_count for item in outcomes)}\n"
        f"    network_detail_requests={sum(item.network_detail_request_count for item in outcomes)}\n"
        f"    elapsed={time.perf_counter() - run_started:.1f}s"
    )
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
            f"selected_details_complete={outcome.selected_details_complete}, observed={outcome.observed_count}, "
            f"selected={outcome.selected_for_detail_count}, skipped={outcome.intentionally_skipped_count}, "
            f"reused={outcome.reused_detail_count}, to_fetch={outcome.details_to_fetch_count}, "
            f"details={outcome.detail_success_count}/{outcome.details_to_fetch_count}"
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
    parser.add_argument("--market-scope", default="config/market_scope.yaml")
    parser.add_argument("--detail-refresh-hours", type=float, default=168.0)
    args = parser.parse_args()
    configs = load_companies(args.config)
    if args.company:
        configs = [item for item in configs if item.company_id in args.company]
    repository = StateRepository(args.database)
    run_id, outcomes, status = run_stateful(
        configs, repository, args.max_jobs, market_scope_path=args.market_scope,
        detail_refresh_hours=args.detail_refresh_hours,
    )
    write_state_report(repository, run_id, outcomes, status, args.report)
    print(json.dumps({"run_id": run_id, "status": status}, indent=2))
    return 0 if status in {"COMPLETED", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
