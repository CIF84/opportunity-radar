from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from opportunity_radar.adapters.base import (
    CountMismatchError, EmptyInventoryError, JobSourceAdapter, SchemaMismatchError,
    clean_text, parse_date, work_mode_from_explicit,
)
from opportunity_radar.models import JobLocation, JobReference, NormalizedJob, utc_now


LIST_QUERY = """query($widgetId: ID!, $filters: [JobAdFilter!]!, $useExampleData: Boolean!, $page: Int, $host: String) { widget(id: $widgetId, useExampleData: $useExampleData, host: $host) { jobAdList(page: $page, filters: $filters) { groupedJobAds { jobAds { id title validFrom locations { city country region } } } paginator { totalNumberOfItems lastPage } } } }"""
DETAIL_QUERY = """query($widgetId: ID!, $jobAdId: ID!, $host: String) { widget(id: $widgetId, host: $host) { jobAd(id: $jobAdId) { id title validFrom content { htmlContent } locations { city country region } employer { companyName } } } }"""


class AlmaCareerAdapter(JobSourceAdapter):
    source = "almacareer"
    api_url = "https://api.capybara.lmc.cz/api/graphql/widget"

    def _credentials(self):
        opts = self.config.options
        if opts.get("widget_id") and opts.get("api_key"):
            return opts["widget_id"], opts["api_key"], opts.get("detail_path", "/detail")
        html = self._request("GET", self.config.endpoint_url).text
        soup = BeautifulSoup(html, "html.parser")
        node = soup.select_one("#vacancies[data-widget], [data-widget]")
        widget_name = opts.get("widget_name") or (node.get("data-widget") if node else "main")
        for script in soup.select("script[src]"):
            text = self._request("GET", urljoin(self.config.endpoint_url, script["src"])).text
            pattern = rf'["\']{re.escape(widget_name)}["\']\s*:\s*\{{[^}}]*?["\']id["\']\s*:\s*["\']([0-9a-f-]{{36}})["\'][^}}]*?["\']apiKey["\']\s*:\s*["\']([0-9a-f]{{64}})["\']([^}}]*)'
            match = re.search(pattern, text, re.I)
            if match:
                detail = re.search(r'["\']detailPath["\']\s*:\s*["\']([^"\']+)', match.group(3))
                return match.group(1), match.group(2), detail.group(1) if detail else "/detail"
        raise SchemaMismatchError(f"{self.config.company_id}: Alma widget credentials not found")

    def _graphql(self, query, variables, api_key):
        payload = self._request("POST", self.config.options.get("api_url", self.api_url), headers={"X-API-KEY": api_key}, json={"query": query, "variables": variables}).json()
        if not isinstance(payload, dict) or payload.get("errors"):
            raise SchemaMismatchError(f"{self.config.company_id}: invalid Alma GraphQL response")
        return payload.get("data", {}).get("widget")

    @staticmethod
    def _locations(raw):
        result = []
        for item in raw or []:
            parts = [item.get(k) for k in ("city", "region", "country") if item.get(k)]
            if parts:
                result.append(JobLocation(raw=", ".join(dict.fromkeys(parts)), city=item.get("city"), region=item.get("region"), country=item.get("country")))
        return result

    def list_jobs(self, company_config):
        widget_id, api_key, detail_path = self._credentials()
        host = self.config.ats_tenant or self.config.endpoint_url.split("/")[2]
        refs, expected, last_page = [], None, 1
        for page in range(1, 1001):
            widget = self._graphql(LIST_QUERY, {"widgetId": widget_id, "filters": [], "useExampleData": False, "page": page, "host": host}, api_key)
            listing = widget.get("jobAdList") if isinstance(widget, dict) else None
            if not isinstance(listing, dict) or not isinstance(listing.get("groupedJobAds", {}).get("jobAds"), list):
                raise SchemaMismatchError(f"{self.config.company_id}: Alma listing schema mismatch")
            paginator = listing.get("paginator") or {}
            expected, last_page = paginator.get("totalNumberOfItems"), paginator.get("lastPage")
            if not isinstance(expected, int) or not isinstance(last_page, int):
                raise SchemaMismatchError(f"{self.config.company_id}: Alma paginator schema mismatch")
            for job in listing["groupedJobAds"]["jobAds"]:
                if not job.get("id") or not job.get("title"):
                    raise SchemaMismatchError(f"{self.config.company_id}: Alma job schema mismatch")
                url = urljoin(self.config.endpoint_url, detail_path) + f"?r=detail&id={job['id']}"
                refs.append(JobReference(self.config.company_id, str(job["id"]), url, {"job": job, "widget_id": widget_id, "api_key": api_key, "host": host}))
            if page >= last_page:
                break
        if expected == 0:
            raise EmptyInventoryError(f"{self.config.company_id}: source explicitly reports zero jobs")
        if len({r.external_job_id for r in refs}) != expected:
            raise CountMismatchError(f"{self.config.company_id}: expected {expected} Alma jobs, extracted {len(refs)}")
        return refs

    def fetch_job(self, ref):
        m = ref.metadata
        widget = self._graphql(DETAIL_QUERY, {"widgetId": m["widget_id"], "jobAdId": ref.external_job_id, "host": m["host"]}, m["api_key"])
        job = widget.get("jobAd") if isinstance(widget, dict) else None
        if not isinstance(job, dict) or not job.get("title"):
            raise SchemaMismatchError(f"{self.config.company_id}: Alma detail schema mismatch")
        return NormalizedJob(self.config.company_id, self.config.company_name, str(job.get("id")), clean_text(job["title"]), self._locations(job.get("locations")), work_mode_from_explicit(), ref.canonical_url, clean_text((job.get("content") or {}).get("htmlContent")), parse_date(job.get("validFrom")), None, None, None, self.source, utc_now())
