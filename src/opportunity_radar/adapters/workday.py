from __future__ import annotations

from urllib.parse import urljoin

from opportunity_radar.config import CompanyConfig
from opportunity_radar.models import JobReference, ListingFacts, NormalizedJob, WorkMode, utc_now

from .base import (
    ConfirmedEmptyInventoryError,
    ExtractionError,
    JobSourceAdapter,
    clean_text,
    locations_from_raw,
    parse_date,
    work_mode_from_explicit,
)


class WorkdayAdapter(JobSourceAdapter):
    source = "workday"

    def __init__(self, config: CompanyConfig, session=None):
        super().__init__(config, session)
        host, tenant, site = config.ats_tenant.split("|")
        self.web_root = f"https://{tenant}.{host}.myworkdayjobs.com/{site}"
        self.api_root = f"https://{tenant}.{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
        self._listing_diagnostic_limit = 0
        self.listing_schema_samples = []
        self.listing_response_diagnostics = []

    def enable_listing_schema_diagnostics(self, sample_size: int) -> None:
        self._listing_diagnostic_limit = max(0, int(sample_size))

    @staticmethod
    def _diagnostic_value(value):
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return value[:500]
        if isinstance(value, list):
            return [WorkdayAdapter._diagnostic_value(item) for item in value[:10]]
        if isinstance(value, dict):
            return {key: WorkdayAdapter._diagnostic_value(item) for key, item in sorted(value.items())}
        return f"<{type(value).__name__}>"

    def list_jobs(self, company_config: CompanyConfig) -> list[JobReference]:
        limit = int(self.config.options.get("page_size", 20))
        offset = 0
        references: list[JobReference] = []
        while True:
            payload = {
                "appliedFacets": self.config.options.get("applied_facets", {}),
                "limit": limit,
                "offset": offset,
                "searchText": self.config.options.get("search_text", ""),
            }
            data = self._request("POST", f"{self.api_root}/jobs", json=payload).json()
            if self._listing_diagnostic_limit and not self.listing_response_diagnostics:
                self.listing_response_diagnostics.append({
                    "keys": sorted(data) if isinstance(data, dict) else [],
                    "total": data.get("total") if isinstance(data, dict) else None,
                    "facets": self._diagnostic_value(data.get("facets")) if isinstance(data, dict) else None,
                    "applied_facets": self._diagnostic_value(payload["appliedFacets"]),
                    "search_text_set": bool(payload["searchText"]),
                })
            postings = data.get("jobPostings")
            if not isinstance(postings, list):
                raise ExtractionError("Workday response has no jobPostings list")
            for item in postings:
                if len(self.listing_schema_samples) < self._listing_diagnostic_limit:
                    self.listing_schema_samples.append({
                        "keys": sorted(item),
                        "types": {key: type(value).__name__ for key, value in sorted(item.items())},
                        "sample": self._diagnostic_value(item),
                    })
                path = item.get("externalPath")
                if not path:
                    continue
                external_id = item.get("bulletFields", [None])[0] if item.get("bulletFields") else None
                locations_text = clean_text(item.get("locationsText"))
                mode = work_mode_from_explicit(item.get("remoteType"), locations_text)
                references.append(
                    JobReference(
                        company_id=company_config.company_id,
                        external_job_id=str(external_id) if external_id else None,
                        canonical_url=urljoin(self.web_root + "/", path.lstrip("/")),
                        metadata={"external_path": path},
                        listing_facts=ListingFacts(
                            title=clean_text(item.get("title")),
                            locations=tuple(locations_from_raw(locations_text)),
                            work_mode=mode if mode is not WorkMode.UNSPECIFIED else None,
                        ),
                    )
                )
            total = int(data.get("total", len(references)))
            offset += len(postings)
            if not postings or offset >= total:
                break
        if not references:
            if total == 0:
                raise ConfirmedEmptyInventoryError("Workday returned a valid but empty inventory")
            raise ExtractionError(
                f"Workday reported {total} jobs but no usable identities were extracted"
            )
        return references

    def fetch_job(self, job_reference: JobReference) -> NormalizedJob:
        path = job_reference.metadata.get("external_path")
        if not path:
            raise ExtractionError("Workday JobReference has no external_path")
        data = self._request("GET", f"{self.api_root}{path}").json().get("jobPostingInfo")
        if not isinstance(data, dict):
            raise ExtractionError("Workday detail response has no jobPostingInfo")
        external_id = data.get("jobReqId") or job_reference.external_job_id
        location_values = data.get("additionalLocations") or []
        if data.get("location"):
            location_values = [data["location"], *location_values]
        return NormalizedJob(
            company_id=self.config.company_id,
            company_name=self.config.company_name,
            external_job_id=str(external_id) if external_id else None,
            title=clean_text(data.get("title")) or "",
            locations=locations_from_raw(location_values),
            work_mode=work_mode_from_explicit(data.get("timeType"), data.get("location"), data.get("additionalLocations")),
            canonical_url=data.get("externalUrl") or job_reference.canonical_url,
            description=clean_text(data.get("jobDescription")),
            date_posted=parse_date(data.get("startDate")),
            valid_through=parse_date(data.get("endDate")),
            employment_type=clean_text(data.get("timeType")),
            department=clean_text(data.get("jobFamily")),
            source=self.source,
            retrieved_at=utc_now(),
        )
