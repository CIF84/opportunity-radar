from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.models import NormalizedJob
from opportunity_radar.phase3_config import Phase3ConfigurationError, Taxonomy
from opportunity_radar.phase3_models import SemanticJobInput
from opportunity_radar.state_repository import StateRepository


@dataclass(frozen=True)
class BenchmarkJobFixture:
    benchmark_id: str
    source_completeness: str
    strict_benchmark_eligible: bool
    notes: str | None
    job: SemanticJobInput


@dataclass(frozen=True)
class BenchmarkCase:
    benchmark_id: str
    company: str
    role_label: str
    fixture: BenchmarkJobFixture
    expected: dict[str, Any]


def semantic_job_from_normalized(job: NormalizedJob) -> SemanticJobInput:
    return SemanticJobInput(
        job.company_name, job.title, job.description or "",
        tuple({"raw": x.raw, "city": x.city, "region": x.region, "country": x.country} for x in job.locations),
        job.work_mode.value, job.employment_type, job.department,
    )


def load_active_semantic_jobs(repository: StateRepository) -> list[tuple[int, int, str, SemanticJobInput]]:
    """Read-only Phase 2 -> Phase 3 boundary using the latest normalized snapshot."""
    with repository.connect() as connection:
        rows = connection.execute(
            """SELECT ji.job_instance_id,jo.job_observation_id,jo.fingerprint,jo.normalized_snapshot
               FROM job_instances ji JOIN job_observations jo
               ON jo.job_observation_id=ji.latest_observation_id
               WHERE ji.lifecycle_state='ACTIVE' ORDER BY ji.job_instance_id"""
        ).fetchall()
    result = []
    for row in rows:
        raw = json.loads(row["normalized_snapshot"])
        job = SemanticJobInput(
            raw["company_name"], raw.get("title"), raw.get("description") or "",
            tuple(raw.get("locations", [])), raw["work_mode"], raw.get("employment_type"),
            raw.get("department"),
        )
        result.append((row["job_instance_id"], row["job_observation_id"], row["fingerprint"], job))
    return result


def load_benchmark_fixture(path: str | Path) -> BenchmarkJobFixture:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    metadata, job = raw["fixture_metadata"], raw["job"]
    completeness = metadata["source_completeness"]
    if completeness not in {"FULL", "DESCRIPTION_COMPLETE_TITLE_UNKNOWN"}:
        raise Phase3ConfigurationError("invalid benchmark source completeness")
    if completeness == "FULL" and not job.get("title"):
        raise Phase3ConfigurationError("FULL benchmark fixture requires a title")
    if job["work_mode"] not in {"onsite", "hybrid", "remote", "unspecified"}:
        raise Phase3ConfigurationError("invalid benchmark work mode")
    supplemental = {key: value for key, value in job.items() if key not in {
        "company_name", "title", "description", "locations", "work_mode", "employment_type",
        "department", "external_job_id", "canonical_url", "date_posted", "valid_through",
    }}
    semantic_job = SemanticJobInput(
        job["company_name"], job.get("title"), job["description"], tuple(job["locations"]),
        job["work_mode"], job.get("employment_type"), job.get("department"), supplemental,
    )
    return BenchmarkJobFixture(
        metadata["benchmark_id"], completeness, bool(metadata["strict_benchmark_eligible"]),
        metadata.get("notes"), semantic_job,
    )


def load_benchmark(path: str | Path, taxonomy: Taxonomy) -> list[BenchmarkCase]:
    benchmark_path = Path(path)
    raw = yaml.safe_load(benchmark_path.read_text(encoding="utf-8"))
    seen: set[str] = set()
    cases = []
    for item in raw["cases"]:
        benchmark_id = item["benchmark_id"]
        if benchmark_id in seen:
            raise Phase3ConfigurationError(f"duplicate benchmark id: {benchmark_id}")
        seen.add(benchmark_id)
        fixture = load_benchmark_fixture(benchmark_path.parent / item["job_fixture"])
        if fixture.benchmark_id != benchmark_id:
            raise Phase3ConfigurationError(f"benchmark fixture id mismatch: {benchmark_id}")
        expected = item["expected"]
        references = list(expected["strengths"]["required_concepts"]) + list(expected["gaps"]["expected_concepts"]) + list(expected["risks"]["expected_categories"])
        for section in ("strengths", "gaps", "risks"):
            additional = expected[section].get("allowed_additional")
            if isinstance(additional, list):
                references.extend(additional)
        for concept in references:
            taxonomy.require(concept, "benchmark concept")
        cases.append(BenchmarkCase(benchmark_id, item["company"], item["role_label"], fixture, expected))
    return cases
