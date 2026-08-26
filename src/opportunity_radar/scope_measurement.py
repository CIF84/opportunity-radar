from __future__ import annotations

import argparse
import json
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opportunity_radar.adapters.base import ConfirmedEmptyInventoryError, PaginationCapError
from opportunity_radar.config import load_companies
from opportunity_radar.registry import AdapterRegistry
from opportunity_radar.scope_selection import (
    SelectionDecision, listing_evidence_counts, listing_facts_fingerprint,
    load_market_scope, select_for_detail,
)


LOCAL_NORMALIZATION_ADAPTERS = {"json_feed", "phenom"}
COUNT_FIELDS = (
    "inventory_total", "listing_title_available", "listing_location_available",
    "structured_country_available", "explicit_czech", "explicit_compatible_remote",
    "remote_eligibility_unknown", "geography_unknown", "explicitly_out_of_scope",
    "selected_for_detail", "projected_normalization_operations",
    "projected_network_detail_requests", "raw_unparsed_geography",
)


def _empty_counts() -> Counter:
    return Counter({field: 0 for field in COUNT_FIELDS})


def _summary(counts: Counter, reasons: Counter, *, completeness: bool) -> dict[str, Any]:
    result = {field: int(counts[field]) for field in COUNT_FIELDS}
    total = result["inventory_total"]
    result["projected_detail_requests"] = result["projected_network_detail_requests"]
    result["projected_request_reduction"] = (
        round(1 - result["projected_network_detail_requests"] / total, 6) if total else None
    )
    result["inventory_completeness_proven"] = completeness
    result["selection_reason_counts"] = dict(sorted(reasons.items()))
    return result


def _measure_references(config, references, scope):
    counts, reasons, evidence = _empty_counts(), Counter(), []
    counts["inventory_total"] = len(references)
    for reference in references:
        facts = reference.listing_facts
        counts.update(listing_evidence_counts(facts, scope))
        selection = select_for_detail(facts, scope)
        reasons[selection.reason] += 1
        if selection.decision is SelectionDecision.SELECT_GEOGRAPHY_UNKNOWN:
            counts["geography_unknown"] += 1
        elif selection.decision is SelectionDecision.SELECT_REMOTE_ELIGIBILITY_UNKNOWN:
            counts["remote_eligibility_unknown"] += 1
        elif selection.decision is SelectionDecision.SKIP_EXPLICITLY_OUT_OF_SCOPE:
            counts["explicitly_out_of_scope"] += 1
        if selection.selected:
            counts["selected_for_detail"] += 1
            counts["projected_normalization_operations"] += 1
            if config.adapter not in LOCAL_NORMALIZATION_ADAPTERS:
                counts["projected_network_detail_requests"] += 1
        evidence.append({
            "company_id": reference.company_id,
            "external_job_id": reference.external_job_id,
            "canonical_url": reference.canonical_url,
            "listing_facts": facts.to_dict(),
            "listing_facts_fingerprint": listing_facts_fingerprint(facts),
            "selection_decision": selection.decision.value,
            "selection_reason": selection.reason,
        })
    return counts, reasons, evidence


def run_scope_measurement(
    companies_path: str | Path = "config/companies.yaml",
    market_scope_path: str | Path = "config/market_scope.yaml",
    output_path: str | Path | None = None,
    run_id: str | None = None,
    workday_schema_sample: int = 0,
    successfactors_diagnostic_pages: int = 0,
) -> tuple[dict[str, Any], Path]:
    configs = load_companies(companies_path)
    scope = load_market_scope(market_scope_path)
    run_id = run_id or f"scope-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    output = Path(output_path) if output_path else Path("output/scope_measurement") / f"{run_id}.json"
    started = time.perf_counter()
    employers, failures, warnings = [], [], []
    adapter_counts: dict[str, Counter] = defaultdict(_empty_counts)
    adapter_reasons: dict[str, Counter] = defaultdict(Counter)
    global_counts, global_reasons = _empty_counts(), Counter()
    all_evidence = []
    listing_schema_diagnostics = []
    source_contract_diagnostics = []
    for index, config in enumerate(configs, 1):
        adapter = None
        employer_started = time.perf_counter()
        print(f"[{index}/{len(configs)}] START company={config.company_id} adapter={config.adapter}", flush=True)
        try:
            adapter = AdapterRegistry.create(config)
            if config.adapter == "workday" and workday_schema_sample:
                adapter.enable_listing_schema_diagnostics(workday_schema_sample)
            if config.adapter == "successfactors" and successfactors_diagnostic_pages:
                adapter.enable_source_diagnostics(successfactors_diagnostic_pages)
            try:
                references = adapter.list_jobs(config)
            except ConfirmedEmptyInventoryError:
                references = []
            counts, reasons, evidence = _measure_references(config, references, scope)
            summary = _summary(counts, reasons, completeness=True)
            employers.append({
                "company_id": config.company_id, "adapter": config.adapter,
                "status": "SUCCESS", **summary,
            })
            global_counts.update(counts); global_reasons.update(reasons)
            adapter_counts[config.adapter].update(counts); adapter_reasons[config.adapter].update(reasons)
            all_evidence.extend(evidence)
            if config.adapter == "workday" and workday_schema_sample:
                listing_schema_diagnostics.append({
                    "company_id": config.company_id,
                    "adapter": config.adapter,
                    "samples": adapter.listing_schema_samples,
                    "responses": adapter.listing_response_diagnostics,
                })
            if config.adapter == "successfactors" and successfactors_diagnostic_pages:
                source_contract_diagnostics.append({
                    "company_id": config.company_id,
                    "adapter": config.adapter,
                    "pages": adapter.source_diagnostics,
                })
            print(
                f"[{index}/{len(configs)}] INVENTORY company={config.company_id} "
                f"jobs={len(references)} selected={counts['selected_for_detail']} "
                f"network_details={counts['projected_network_detail_requests']} "
                f"elapsed={time.perf_counter() - employer_started:.1f}s",
                flush=True,
            )
        except Exception as exc:
            if config.adapter == "successfactors" and successfactors_diagnostic_pages and adapter is not None:
                source_contract_diagnostics.append({
                    "company_id": config.company_id,
                    "adapter": config.adapter,
                    "pages": getattr(adapter, "source_diagnostics", []),
                    "listing_error_type": type(exc).__name__,
                })
            adapter_counts[config.adapter].update(_empty_counts())
            warning = isinstance(exc, PaginationCapError)
            failure = {
                "company_id": config.company_id, "adapter": config.adapter,
                "error_type": type(exc).__name__, "error_message": str(exc),
                "pagination_cap_warning": warning,
            }
            failures.append(failure)
            if warning:
                warnings.append(failure)
            employers.append({
                "company_id": config.company_id, "adapter": config.adapter,
                "status": "FAILED", **_summary(_empty_counts(), Counter(), completeness=False),
                "error_type": type(exc).__name__, "error_message": str(exc),
            })
            print(
                f"[{index}/{len(configs)}] FAIL company={config.company_id} "
                f"error_type={type(exc).__name__} elapsed={time.perf_counter() - employer_started:.1f}s",
                flush=True,
            )
    successful = [item for item in employers if item["status"] == "SUCCESS"]
    artifact = {
        "experiment": "pre-detail-scope-measurement-v1",
        "measurement_run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "companies_configuration": str(companies_path),
        "market_scope_configuration": str(market_scope_path),
        "market_scope_version": scope.version,
        "zero_detail_requests": True,
        "zero_semantic_calls": True,
        "zero_phase2_state_writes": True,
        "global": _summary(
            global_counts, global_reasons,
            completeness=len(successful) == len(configs) and all(item["inventory_completeness_proven"] for item in successful),
        ),
        "employers": employers,
        "adapters": {
            adapter: _summary(
                counts, adapter_reasons[adapter],
                completeness=all(
                    item["inventory_completeness_proven"]
                    for item in employers if item["adapter"] == adapter
                ),
            )
            for adapter, counts in sorted(adapter_counts.items())
        },
        "listing_failures": failures,
        "pagination_cap_warnings": warnings,
        "listing_schema_diagnostics": listing_schema_diagnostics,
        "source_contract_diagnostics": source_contract_diagnostics,
        "references": all_evidence,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "limitations": [
            "Unknown or unparsed geography is retained, never treated as incompatible.",
            "Title is recorded but is not used for exclusion.",
            "Projected network detail requests distinguish local normalization in JSON feed and Phenom adapters.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(artifact, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        "MEASUREMENT SUMMARY\n"
        f"    employers={len(configs)}\n"
        f"    listing_failures={len(failures)}\n"
        f"    inventory_total={global_counts['inventory_total']}\n"
        f"    selected_for_detail={global_counts['selected_for_detail']}\n"
        f"    projected_network_detail_requests={global_counts['projected_network_detail_requests']}\n"
        f"    elapsed={artifact['elapsed_seconds']:.1f}s\n"
        f"    output={output}",
        flush=True,
    )
    return artifact, output


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure conservative pre-detail market scope without fetching details")
    parser.add_argument("--companies", default="config/companies.yaml")
    parser.add_argument("--market-scope", default="config/market_scope.yaml")
    parser.add_argument("--output")
    parser.add_argument("--run-id")
    parser.add_argument("--workday-schema-sample", type=int, default=0)
    parser.add_argument("--successfactors-diagnostic-pages", type=int, default=0)
    args = parser.parse_args()
    artifact, _ = run_scope_measurement(
        args.companies, args.market_scope, args.output, args.run_id,
        args.workday_schema_sample, args.successfactors_diagnostic_pages,
    )
    return 0 if not artifact["listing_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
