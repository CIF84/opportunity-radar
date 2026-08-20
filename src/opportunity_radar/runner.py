from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opportunity_radar.adapters.base import EmptyInventoryError
from opportunity_radar.config import CompanyConfig, load_companies
from opportunity_radar.models import NormalizedJob
from opportunity_radar.registry import AdapterRegistry


@dataclass
class EmployerResult:
    company_id: str
    company_name: str
    adapter: str
    status: str
    references_found: int = 0
    jobs_normalized: int = 0
    detail_failures: int = 0
    error: str | None = None
    jobs: list[NormalizedJob] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in self.__dict__.items() if key != "jobs"}


def ingest_company(config: CompanyConfig, max_jobs: int | None = None) -> EmployerResult:
    try:
        adapter = AdapterRegistry.create(config)
        references = adapter.list_jobs(config)
        jobs: list[NormalizedJob] = []
        failures = []
        selected = references[:max_jobs] if max_jobs else references
        for reference in selected:
            try:
                jobs.append(adapter.fetch_job(reference))
            except Exception as exc:  # isolated source/detail failure is an explicit spike result
                failures.append(f"{reference.canonical_url}: {type(exc).__name__}: {exc}")
        if not jobs:
            return EmployerResult(
                config.company_id,
                config.company_name,
                config.adapter,
                "FAIL",
                len(references),
                0,
                len(failures),
                "; ".join(failures[:3]) or "no details normalized",
            )
        status = "PASS" if not failures else "PARTIAL"
        return EmployerResult(
            config.company_id,
            config.company_name,
            config.adapter,
            status,
            len(references),
            len(jobs),
            len(failures),
            "; ".join(failures[:3]) or None,
            jobs,
        )
    except EmptyInventoryError as exc:
        return EmployerResult(config.company_id, config.company_name, config.adapter, "EMPTY", error=str(exc))
    except Exception as exc:
        return EmployerResult(
            config.company_id,
            config.company_name,
            config.adapter,
            "FAIL",
            error=f"{type(exc).__name__}: {exc}",
        )


def research_coverage(research_path: str | Path, passing_adapters: set[str]) -> dict[str, Any]:
    family_map = {
        "workday": "workday",
        "greenhouse": "greenhouse",
        "almacareer": "almacareer",
        "successfactors": "successfactors",
        "phenom": "phenom",
        "jibe": "json_feed",
        "json_feed": "json_feed",
        "custom": "generic_html",
    }
    with Path(research_path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    counts = Counter(row["ats_family"] for row in rows)
    covered = [row for row in rows if family_map.get(row["ats_family"]) in passing_adapters]
    bespoke = [row for row in rows if row["bespoke_code_required"].lower() == "yes"]
    return {
        "dataset_employers": len(rows),
        "family_counts": dict(sorted(counts.items())),
        "theoretically_covered": len(covered),
        "theoretical_coverage_rate": len(covered) / len(rows) if rows else 0,
        "research_bespoke_count": len(bespoke),
        "research_bespoke_rate": len(bespoke) / len(rows) if rows else 0,
    }


def build_summary(results: list[EmployerResult], research_path: str | Path) -> dict[str, Any]:
    jobs = [job for result in results for job in result.jobs]
    successful = [result for result in results if result.status in {"PASS", "PARTIAL"}]
    grouped: dict[str, list[EmployerResult]] = defaultdict(list)
    for result in results:
        grouped[result.adapter].append(result)
    adapter_metrics = {
        adapter: {
            "tested": len(items),
            "successful": sum(item.status in {"PASS", "PARTIAL"} for item in items),
            "success_rate": sum(item.status in {"PASS", "PARTIAL"} for item in items) / len(items),
        }
        for adapter, items in sorted(grouped.items())
    }
    fields = {
        "company": lambda job: bool(job.company_id and job.company_name),
        "title": lambda job: bool(job.title),
        "location": lambda job: bool(job.locations),
        "canonical_url": lambda job: bool(job.canonical_url),
        "external_job_id": lambda job: bool(job.external_job_id),
        "description": lambda job: bool(job.description),
        "date_posted": lambda job: bool(job.date_posted),
    }
    completeness = {
        field: sum(predicate(job) for job in jobs) / len(jobs) if jobs else 0
        for field, predicate in fields.items()
    }
    passing_adapters = {
        name
        for name, metric in adapter_metrics.items()
        if metric["tested"] >= 2 and metric["success_rate"] == 1.0
    }
    return {
        "employers_tested": len(results),
        "employers_successful": len(successful),
        "employer_success_rate": len(successful) / len(results) if results else 0,
        "jobs_normalized": len(jobs),
        "adapter_metrics": adapter_metrics,
        "field_completeness": completeness,
        "research_coverage": research_coverage(research_path, passing_adapters),
    }


def write_outputs(results, output_dir: str | Path, research_path: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    jobs = [job.to_dict() for result in results for job in result.jobs]
    summary = build_summary(results, research_path)
    (output / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "run_results.json").write_text(
        json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "OPPORTUNITY RADAR — INGESTION FEASIBILITY SPIKE",
        "",
        f"Employers tested: {summary['employers_tested']}",
        f"Successful: {summary['employers_successful']}",
        f"Success rate: {summary['employer_success_rate']:.1%}",
        f"Jobs normalized: {summary['jobs_normalized']}",
        "",
    ]
    for adapter, metric in summary["adapter_metrics"].items():
        lines.append(
            f"{adapter}: {metric['successful']}/{metric['tested']} ({metric['success_rate']:.1%})"
        )
        for result in (item for item in results if item.adapter == adapter):
            suffix = f" — {result.error}" if result.error else ""
            lines.append(
                f"  {result.company_name}: {result.status}, {result.references_found} references, "
                f"{result.jobs_normalized} details{suffix}"
            )
        lines.append("")
    lines.extend(
        [
            "FIELD COMPLETENESS",
            *[f"{field}: {rate:.1%}" for field, rate in summary["field_completeness"].items()],
            "",
            "See docs/ingestion_feasibility_report.md for research corrections, coverage analysis,",
            "and the ingestion-architecture GO recommendation.",
        ]
    )
    (output / "ingestion_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ingestion feasibility spike")
    parser.add_argument("--config", default="config/companies.yaml")
    parser.add_argument("--research", default="research/target_companies.csv")
    parser.add_argument("--output", default="output")
    parser.add_argument("--max-jobs", type=int, default=None)
    parser.add_argument("--company", action="append", default=[])
    args = parser.parse_args()
    configs = load_companies(args.config)
    if args.company:
        configs = [config for config in configs if config.company_id in args.company]
    results = [ingest_company(config, args.max_jobs) for config in configs]
    summary = write_outputs(results, args.output, args.research)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(result.status in {"PASS", "PARTIAL"} for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
