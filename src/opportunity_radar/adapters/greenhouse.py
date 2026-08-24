from __future__ import annotations

from opportunity_radar.config import CompanyConfig
from opportunity_radar.models import JobReference, NormalizedJob, utc_now

from .base import (
    ConfirmedEmptyInventoryError,
    ExtractionError,
    JobSourceAdapter,
    clean_text,
    locations_from_raw,
    parse_date,
    work_mode_from_explicit,
)


class GreenhouseAdapter(JobSourceAdapter):
    source = "greenhouse"

    @property
    def api_root(self) -> str:
        return f"https://boards-api.greenhouse.io/v1/boards/{self.config.ats_tenant}"

    def list_jobs(self, company_config: CompanyConfig) -> list[JobReference]:
        data = self._request("GET", f"{self.api_root}/jobs").json()
        jobs = data.get("jobs")
        if not isinstance(jobs, list):
            raise ExtractionError("Greenhouse response has no jobs list")
        if not jobs:
            raise ConfirmedEmptyInventoryError("Greenhouse returned a valid but empty inventory")
        return [
            JobReference(
                company_id=company_config.company_id,
                external_job_id=str(job["id"]),
                canonical_url=job["absolute_url"],
                metadata={"api_url": f"{self.api_root}/jobs/{job['id']}"},
            )
            for job in jobs
            if job.get("id") and job.get("absolute_url")
        ]

    def fetch_job(self, job_reference: JobReference) -> NormalizedJob:
        url = job_reference.metadata.get("api_url") or f"{self.api_root}/jobs/{job_reference.external_job_id}"
        job = self._request("GET", url).json()
        offices = [item.get("name") for item in job.get("offices", []) if item.get("name")]
        location = job.get("location", {}).get("name")
        raw_locations = offices or ([location] if location else [])
        return NormalizedJob(
            company_id=self.config.company_id,
            company_name=self.config.company_name,
            external_job_id=str(job.get("id")) if job.get("id") is not None else job_reference.external_job_id,
            title=clean_text(job.get("title")) or "",
            locations=locations_from_raw(raw_locations),
            work_mode=work_mode_from_explicit(location, offices),
            canonical_url=job.get("absolute_url") or job_reference.canonical_url,
            description=clean_text(job.get("content")),
            date_posted=parse_date(job.get("updated_at")),
            valid_through=None,
            employment_type=None,
            department=clean_text(", ".join(d["name"] for d in job.get("departments", []) if d.get("name"))),
            source=self.source,
            retrieved_at=utc_now(),
        )
