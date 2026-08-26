from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from opportunity_radar.config import CompanyConfig
from opportunity_radar.models import JobLocation, JobReference, ListingFacts, NormalizedJob, WorkMode, utc_now

from .base import UnvalidatedEmptyInventoryError, ExtractionError, JobSourceAdapter, PaginationCapError, clean_text, locations_from_raw, parse_date, work_mode_from_explicit
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


def _jsonld_listing_locations(data: dict[str, Any]):
    value = data.get("jobLocation") or []
    locations = value if isinstance(value, list) else [value]
    result = []
    for item in locations:
        if not isinstance(item, dict):
            continue
        address = item.get("address", item)
        if not isinstance(address, dict):
            continue
        city, region, country = (
            address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")
        )
        raw = ", ".join(str(part) for part in (city, region, country) if part)
        if raw:
            result.append(JobLocation(raw, city=city, region=region, country=country))
    return tuple(result)


class GenericHtmlAdapter(JobSourceAdapter):
    source = "generic_html"

    def enable_source_diagnostics(self, max_pages: int = 2) -> None:
        self._source_diagnostic_limit = max(0, int(max_pages))
        self.source_diagnostics = []

    @staticmethod
    def _safe_value(name: str, value: Any) -> str | list[str] | None:
        if value is None:
            return None
        if re.search(r"token|secret|csrf|api.?key", name, re.I):
            return "<redacted>"
        if isinstance(value, list):
            return [str(item)[:200] for item in value[:10]]
        return str(value)[:500]

    @classmethod
    def _safe_url(cls, value: str, base: str) -> str:
        absolute = urljoin(base, value)
        parts = urlsplit(absolute)
        query = []
        for key, item in parse_qsl(parts.query, keep_blank_values=True):
            query.append((key, cls._safe_value(key, item) or ""))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))[:1000]

    def _capture_source_diagnostic(self, response, soup, page: int, params) -> None:
        limit = getattr(self, "_source_diagnostic_limit", 0)
        diagnostics = getattr(self, "source_diagnostics", None)
        if not limit or diagnostics is None or len(diagnostics) >= limit:
            return
        pagination_links = []
        for link in soup.select("a[href]"):
            href = str(link.get("href"))
            marker = " ".join((href, " ".join(link.get("class", [])), link.get_text(" ", strip=True)))
            if re.search(r"startrow|page|pagination|next|previous", marker, re.I):
                pagination_links.append({
                    "text": link.get_text(" ", strip=True)[:200],
                    "href": self._safe_url(href, response.url),
                    "rel": list(link.get("rel", [])),
                })
            if len(pagination_links) >= 25:
                break
        hidden_fields = []
        for node in soup.select('input[type="hidden"]')[:30]:
            name = str(node.get("name") or node.get("id") or "")
            hidden_fields.append({
                "name": name[:200], "id": str(node.get("id") or "")[:200],
                "value": self._safe_value(name, node.get("value")),
            })
        total_candidates = []
        for node in soup.find_all(True):
            marker = " ".join((str(node.get("id") or ""), " ".join(node.get("class", []))))
            text = node.get_text(" ", strip=True)
            if re.search(r"total|result.?count|search.?result", marker, re.I) and re.search(r"\d", text):
                total_candidates.append({"tag": node.name, "marker": marker[:300], "text": text[:300]})
            if len(total_candidates) >= 20:
                break
        filter_controls = []
        for node in soup.select("input, select"):
            marker = " ".join((str(node.get("name") or ""), str(node.get("id") or "")))
            if re.search(r"location|country", marker, re.I):
                options = [
                    {"value": self._safe_value("value", option.get("value")), "text": option.get_text(" ", strip=True)[:200]}
                    for option in node.select("option")[:20]
                ]
                filter_controls.append({
                    "tag": node.name, "name": str(node.get("name") or "")[:200],
                    "id": str(node.get("id") or "")[:200],
                    "value": self._safe_value(str(node.get("name") or ""), node.get("value")),
                    "options": options,
                })
            if len(filter_controls) >= 20:
                break
        data_attributes = []
        for node in soup.find_all(True):
            relevant = {
                key: self._safe_value(key, value)
                for key, value in node.attrs.items()
                if key.startswith("data-") and re.search(r"total|count|page|location|country|search|url|endpoint|api", key, re.I)
            }
            if relevant:
                data_attributes.append({"tag": node.name, "id": str(node.get("id") or "")[:200], "attributes": relevant})
            if len(data_attributes) >= 30:
                break
        endpoints = []
        endpoint_pattern = re.compile(r'''["']((?:https?://|/)[^"']{1,500})["']''')
        for script in soup.select("script")[:50]:
            if script.get("src"):
                candidate_values = [str(script["src"])]
            else:
                candidate_values = endpoint_pattern.findall((script.string or script.get_text())[:200000])
            for candidate in candidate_values:
                if re.search(r"api|ajax|json|search|job|career", candidate, re.I):
                    safe = self._safe_url(candidate, response.url)
                    if safe not in endpoints:
                        endpoints.append(safe)
                if len(endpoints) >= 30:
                    break
            if len(endpoints) >= 30:
                break
        diagnostics.append({
            "page_index": page,
            "response_url": self._safe_url(response.url, response.url),
            "request_params": {key: self._safe_value(key, value) for key, value in (params or {}).items()},
            "pagination_links": pagination_links,
            "hidden_fields": hidden_fields,
            "total_result_candidates": total_candidates,
            "location_country_filter_controls": filter_controls,
            "relevant_data_attributes": data_attributes,
            "referenced_public_endpoints": endpoints,
        })

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
        pagination_mode = pagination.get("mode", "offset_param")
        safety_max_pages = int(pagination.get("safety_max_pages", 1000))
        pages_to_request = safety_max_pages + 1 if pagination else 1
        next_url = company_config.endpoint_url
        for page in range(pages_to_request):
            params = None
            if pagination and pagination_mode == "offset_param":
                params = {
                    pagination["param"]: int(pagination.get("start", 0))
                    + page * int(pagination.get("step", 1))
                }
            response = self._request("GET", next_url, params=params)
            soup = BeautifulSoup(response.text, "html.parser")
            self._capture_source_diagnostic(response, soup, page, params)
            page_references: list[JobReference] = []
            for data in jobposting_json_ld(soup):
                url = data.get("url") or data.get("sameAs")
                if url:
                    url = urljoin(response.url, str(url))
                    external_id = data.get("identifier")
                    if isinstance(external_id, dict):
                        external_id = external_id.get("value")
                    mode = work_mode_from_explicit(data.get("jobLocationType"), data.get("title"))
                    page_references.append(JobReference(
                        company_config.company_id,
                        str(external_id) if external_id else self._external_id(url),
                        url,
                        listing_facts=ListingFacts(
                            title=clean_text(data.get("title")),
                            locations=_jsonld_listing_locations(data),
                            work_mode=mode if mode is not WorkMode.UNSPECIFIED else None,
                            department=clean_text(data.get("industry")),
                            employment_type=clean_text(data.get("employmentType")),
                            date_posted=parse_date(data.get("datePosted")),
                        ),
                    ))
            for item in selector_refs(soup, response.url, company_config.options.get("selectors", {})):
                mode = work_mode_from_explicit(item["location"])
                page_references.append(
                    JobReference(
                        company_config.company_id,
                        item["external_id"] or self._external_id(item["url"]),
                        item["url"],
                        metadata={"title": item["title"], "location": item["location"]},
                        listing_facts=ListingFacts(
                            title=clean_text(item["title"]),
                            locations=tuple(locations_from_raw(item["location"])),
                            work_mode=mode if mode is not WorkMode.UNSPECIFIED else None,
                        ),
                    )
                )
            if pagination and page == safety_max_pages:
                if page_references:
                    raise PaginationCapError(
                        f"{self.config.company_id}: pagination safety ceiling {safety_max_pages} reached and the probe page is non-empty"
                    )
                break
            previous = len({ref.canonical_url for ref in references})
            references.extend(page_references)
            current = len({ref.canonical_url for ref in references})
            if pagination and page_references and current == previous:
                raise PaginationCapError(
                    f"{self.config.company_id}: pagination repeated before an empty page proved completeness"
                )
            if not pagination or not page_references:
                break
            if pagination_mode == "discovered_offset_link":
                discovered = self._next_offset_link(soup, response.url, company_config.endpoint_url)
                if discovered is None:
                    break
                next_url = discovered
        unique = {ref.canonical_url: ref for ref in references}
        if not unique:
            raise UnvalidatedEmptyInventoryError("generic HTML extraction found no job references")
        return list(unique.values())

    @staticmethod
    def _offset_from_url(url: str, base_url: str | None = None) -> int:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        if str(query.get("startrow", "")).isdigit():
            return int(query["startrow"])
        path = parts.path.rstrip("/")
        if base_url:
            base_path = urlsplit(base_url).path.rstrip("/")
            if path == base_path:
                return 0
            if path.startswith(base_path + "/"):
                path = path[len(base_path):]
        segments = [part for part in path.split("/") if part]
        return int(segments[-1]) if segments and segments[-1].isdigit() else 0

    @classmethod
    def _next_offset_link(cls, soup, response_url: str, base_url: str | None = None) -> str | None:
        """Follow the smallest advertised forward offset, whether path- or query-based."""
        current = cls._offset_from_url(response_url, base_url)
        candidates = []
        response_host = urlsplit(response_url).netloc
        for link in soup.select("a[href]"):
            candidate = urljoin(response_url, str(link.get("href")))
            if urlsplit(candidate).netloc != response_host:
                continue
            offset = cls._offset_from_url(candidate, base_url)
            if offset > current:
                candidates.append((offset, candidate))
        return min(candidates)[1] if candidates else None

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
