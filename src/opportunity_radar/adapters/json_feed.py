from __future__ import annotations

import math

from opportunity_radar.adapters.base import ConfirmedEmptyInventoryError, CountMismatchError, JobSourceAdapter, SchemaMismatchError, UnvalidatedEmptyInventoryError, clean_text, locations_from_raw, parse_date, value_at_path, work_mode_from_explicit
from opportunity_radar.models import JobReference, NormalizedJob, utc_now


class JsonFeedAdapter(JobSourceAdapter):
    source = "json_feed"

    def _field(self, item, name, default=None):
        return value_at_path(item, self.config.options.get("fields", {}).get(name), default)

    def list_jobs(self, company_config):
        o = self.config.options
        pagination = o.get("pagination", {})
        page, refs, expected, max_pages = pagination.get("start", 1), [], None, None
        for _ in range(pagination.get("safety_max_pages", 1000)):
            params = dict(o.get("query_params", {}))
            params[pagination.get("page_param", "page")] = page
            response = self._request(o.get("method", "GET").upper(), self.config.endpoint_url, params=params, json=o.get("body") if "body" in o else None).json()
            items = value_at_path(response, o.get("items_path"))
            if not isinstance(items, list):
                raise SchemaMismatchError(f"{self.config.company_id}: JSON item path is not a list")
            count = value_at_path(response, pagination["count_path"]) if pagination.get("count_path") else None
            pages = value_at_path(response, pagination["pages_path"]) if pagination.get("pages_path") else None
            if count is not None:
                if not isinstance(count, int):
                    raise SchemaMismatchError(f"{self.config.company_id}: JSON count is not an integer")
                expected = count
            if pages is not None:
                if not isinstance(pages, int):
                    raise SchemaMismatchError(f"{self.config.company_id}: JSON page count is not an integer")
                max_pages = pages
            for item in items:
                title, url = self._field(item, "title"), self._field(item, "canonical_url")
                if not title or not url:
                    raise SchemaMismatchError(f"{self.config.company_id}: mapped title/canonical_url missing")
                external_id = self._field(item, "external_job_id")
                refs.append(JobReference(self.config.company_id, str(external_id) if external_id is not None else None, str(url), {"item": item}))
            if max_pages is None and expected is not None and items:
                max_pages = math.ceil(expected / len(items))
            if not items or (max_pages is not None and page >= max_pages):
                break
            page += pagination.get("step", 1)
        if expected == 0:
            raise ConfirmedEmptyInventoryError(f"{self.config.company_id}: source explicitly reports zero jobs")
        if expected is not None and len(refs) != expected:
            raise CountMismatchError(f"{self.config.company_id}: expected {expected} JSON jobs, extracted {len(refs)}")
        if not refs:
            raise UnvalidatedEmptyInventoryError(f"{self.config.company_id}: no jobs and no validated zero count")
        return refs

    def fetch_job(self, ref):
        item = ref.metadata["item"]
        values = self._field(item, "locations", [])
        if isinstance(values, dict):
            values = list(values.values())
        return NormalizedJob(self.config.company_id, self.config.company_name, ref.external_job_id, clean_text(self._field(item, "title")), locations_from_raw(values), work_mode_from_explicit(self._field(item, "work_mode")), ref.canonical_url, clean_text(self._field(item, "description")), parse_date(self._field(item, "date_posted")), parse_date(self._field(item, "valid_through")), clean_text(self._field(item, "employment_type")), clean_text(self._field(item, "department")), self.source, utc_now())
