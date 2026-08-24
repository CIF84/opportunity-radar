from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from opportunity_radar.config import CompanyConfig
from opportunity_radar.models import JobReference, NormalizedJob, utc_now

from .base import UnvalidatedEmptyInventoryError, ExtractionError, JobSourceAdapter, clean_text, locations_from_raw, parse_date, work_mode_from_explicit
from .html import id_from_url, jobposting_json_ld, selector_refs


def _jsonld_locations(data: dict[str, Any]) -> list[str]:
    value = data.get("jobLocation") or []
    locations = value if isinstance(value, list) else [value]
    result = []
    for item in locations:
        if not isinstance(item, dict):
            continue
        address = item.get("address", item)
        if isinstance(address, dict):
            parts = [address.get(key) for key in ("addressLocality", "addressRegion", "addressCountry")]
            raw = ", ".join(str(part) for part in parts if part)
            if raw:
                result.append(raw)
    return result


class GenericHtmlAdapter(JobSourceAdapter):
    source = "generic_html"

    def _external_id(self, url: str) -> str | None:
        pattern = self.config.options.get("external_id_pattern")
        if pattern:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return id_from_url(url)

    def list_jobs(self, company_config: CompanyConfig) -> list[JobReference]:
        references: list[JobReference] = []
        pagination = company_config.options.get("pagination") or {}
        max_pages = int(pagination.get("max_pages", 1))
        for page in range(max_pages):
            params = None
            if pagination:
                params = {
                    pagination["param"]: int(pagination.get("start", 0))
                    + page * int(pagination.get("step", 1))
                }
            response = self._request("GET", company_config.endpoint_url, params=params)
            soup = BeautifulSoup(response.text, "html.parser")
            page_references: list[JobReference] = []
            for data in jobposting_json_ld(soup):
                url = data.get("url") or data.get("sameAs")
                if url:
                    url = urljoin(response.url, str(url))
                    external_id = data.get("identifier")
                    if isinstance(external_id, dict):
                        external_id = external_id.get("value")
                    page_references.append(JobReference(company_config.company_id, str(external_id) if external_id else self._external_id(url), url))
            for item in selector_refs(soup, response.url, company_config.options.get("selectors", {})):
                page_references.append(
                    JobReference(
                        company_config.company_id,
                        item["external_id"] or self._external_id(item["url"]),
                        item["url"],
                        metadata={"title": item["title"], "location": item["location"]},
                    )
                )
            previous = len({ref.canonical_url for ref in references})
            references.extend(page_references)
            current = len({ref.canonical_url for ref in references})
            if not pagination or not page_references or current == previous:
                break
        unique = {ref.canonical_url: ref for ref in references}
        if not unique:
            raise UnvalidatedEmptyInventoryError("generic HTML extraction found no job references")
        return list(unique.values())

    def fetch_job(self, job_reference: JobReference) -> NormalizedJob:
        response = self._request("GET", job_reference.canonical_url)
        soup = BeautifulSoup(response.text, "html.parser")
        postings = jobposting_json_ld(soup)
        data = postings[0] if postings else {}
        title = data.get("title") or job_reference.metadata.get("title")
        if not title:
            selector = self.config.options.get("detail_selectors", {}).get("title", "h1")
            node = soup.select_one(selector)
            title = node.get_text(" ", strip=True) if node else None
        if not title:
            raise ExtractionError("generic detail extraction found no title")
        raw_locations = _jsonld_locations(data)
        fallback_location = job_reference.metadata.get("location")
        if not raw_locations and fallback_location:
            raw_locations = [fallback_location]
        description = data.get("description")
        detail_selectors = self.config.options.get("detail_selectors", {})
        if not description:
            selector = detail_selectors.get("description")
            node = soup.select_one(selector) if selector else None
            description = str(node) if node else None
        date_posted = data.get("datePosted")
        if not date_posted and detail_selectors.get("date_posted"):
            node = soup.select_one(detail_selectors["date_posted"])
            date_posted = node.get_text(" ", strip=True) if node else None
        external_id = data.get("identifier")
        if isinstance(external_id, dict):
            external_id = external_id.get("value")
        return NormalizedJob(
            company_id=self.config.company_id,
            company_name=self.config.company_name,
            external_job_id=str(external_id) if external_id else job_reference.external_job_id,
            title=clean_text(str(title)) or "",
            locations=locations_from_raw(raw_locations),
            work_mode=work_mode_from_explicit(data.get("jobLocationType"), data.get("title")),
            canonical_url=str(data.get("url") or response.url),
            description=clean_text(description),
            date_posted=parse_date(date_posted),
            valid_through=parse_date(data.get("validThrough")),
            employment_type=clean_text(data.get("employmentType")),
            department=clean_text(data.get("industry")),
            source=self.source,
            retrieved_at=utc_now(),
        )
