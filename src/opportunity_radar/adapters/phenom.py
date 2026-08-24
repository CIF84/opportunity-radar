from __future__ import annotations

import re

from opportunity_radar.adapters.base import ConfirmedEmptyInventoryError, CountMismatchError, JobSourceAdapter, SchemaMismatchError, clean_text, locations_from_raw, parse_date, work_mode_from_explicit
from opportunity_radar.models import JobReference, NormalizedJob, utc_now


class PhenomAdapter(JobSourceAdapter):
    source = "phenom"

    @staticmethod
    def _slug(value):
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    def list_jobs(self, company_config):
        o, offset, refs, expected = self.config.options, 0, [], None
        size = o.get("page_size", 50)
        for _ in range(o.get("safety_max_pages", 1000)):
            body = {"lang": o.get("lang", "en_global"), "deviceType": "desktop", "country": "global", "pageName": "search-results", "ddoKey": "refineSearch", "sortBy": o.get("sort_by", "Most recent"), "subsearch": "", "from": offset, "jobs": True, "counts": True, "all_fields": o.get("all_fields", ["category", "country", "state", "city"]), "size": size, "clearAll": False}
            body.update(o.get("body", {}))
            payload = self._request("POST", self.config.endpoint_url, json=body).json()
            data = payload.get("refineSearch") if isinstance(payload, dict) else None
            jobs = data.get("data", {}).get("jobs") if isinstance(data, dict) else None
            total = data.get("totalHits") if isinstance(data, dict) else None
            if data is None or data.get("status") != 200 or not isinstance(jobs, list) or not isinstance(total, int):
                raise SchemaMismatchError(f"{self.config.company_id}: Phenom refineSearch schema mismatch")
            expected = total
            for job in jobs:
                job_id, title = job.get("jobId") or job.get("reqId"), job.get("title")
                if not job_id or not title:
                    raise SchemaMismatchError(f"{self.config.company_id}: Phenom job schema mismatch")
                url = o["canonical_url_template"].format(jobId=job_id, reqId=job.get("reqId", ""), title_slug=self._slug(title))
                refs.append(JobReference(self.config.company_id, str(job_id), url, {"job": job}))
            offset += len(jobs)
            if offset >= total or not jobs:
                break
        if expected == 0:
            raise ConfirmedEmptyInventoryError(f"{self.config.company_id}: source explicitly reports zero jobs")
        if expected is None or len(refs) != expected:
            raise CountMismatchError(f"{self.config.company_id}: expected {expected} Phenom jobs, extracted {len(refs)}")
        return refs

    def fetch_job(self, ref):
        j = ref.metadata["job"]
        locations = j.get("multi_location") or j.get("location") or [", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)]
        return NormalizedJob(self.config.company_id, self.config.company_name, ref.external_job_id, clean_text(j["title"]), locations_from_raw(locations), work_mode_from_explicit(j.get("RemoteType"), j.get("type")), ref.canonical_url, clean_text(j.get("description") or j.get("descriptionTeaser")), parse_date(j.get("postedDate")), None, clean_text(j.get("type")), clean_text(j.get("category")), self.source, utc_now())
