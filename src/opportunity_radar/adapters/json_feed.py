from __future__ import annotations

import math
from typing import Any

from bs4 import BeautifulSoup

from opportunity_radar.adapters.base import ConfirmedEmptyInventoryError, CountMismatchError, JobSourceAdapter, PaginationCapError, SchemaMismatchError, UnvalidatedEmptyInventoryError, clean_text, locations_from_raw, parse_date, parse_datetime, value_at_path, work_mode_from_explicit
from opportunity_radar.models import JobReference, ListingFacts, NormalizedJob, WorkMode, utc_now


class JsonFeedAdapter(JobSourceAdapter):
    source = "json_feed"

    _MISSING = object()

    def _field(self, item, name, default=None):
        path = self.config.options.get("fields", {}).get(name)
        return value_at_path(item, path, default) if path else default

    def _nested_items(self, response: Any) -> list[dict[str, Any]] | None:
        """Project nested child records into an explicit item/parent context."""
        nested = self.config.options.get("nested_items")
        if nested is None:
            return None
        required = {"groups_path", "items_path"}
        allowed = required | {"group_count_path", "parent_context"}
        if not isinstance(nested, dict) or not required <= set(nested) or set(nested) - allowed:
            raise SchemaMismatchError(
                f"{self.config.company_id}: invalid nested_items configuration"
            )
        parent_paths = nested.get("parent_context", {})
        if not isinstance(parent_paths, dict) or any(
            not isinstance(name, str) or not name or not isinstance(path, str)
            for name, path in parent_paths.items()
        ):
            raise SchemaMismatchError(
                f"{self.config.company_id}: invalid nested parent_context configuration"
            )
        groups = value_at_path(response, nested["groups_path"], self._MISSING)
        if not isinstance(groups, list):
            raise SchemaMismatchError(
                f"{self.config.company_id}: configured nested group path is not a list"
            )
        records: list[dict[str, Any]] = []
        for group_index, group in enumerate(groups):
            if not isinstance(group, dict):
                raise SchemaMismatchError(
                    f"{self.config.company_id}: nested group {group_index} is not an object"
                )
            children = value_at_path(group, nested["items_path"], self._MISSING)
            if not isinstance(children, list):
                raise SchemaMismatchError(
                    f"{self.config.company_id}: nested child path is not a list in group {group_index}"
                )
            count_path = nested.get("group_count_path")
            if count_path:
                expected = value_at_path(group, count_path, self._MISSING)
                if not isinstance(expected, int) or isinstance(expected, bool):
                    raise SchemaMismatchError(
                        f"{self.config.company_id}: nested group count is not an integer in group {group_index}"
                    )
                if expected != len(children):
                    raise CountMismatchError(
                        f"{self.config.company_id}: nested group {group_index} expected "
                        f"{expected} jobs, extracted {len(children)}"
                    )
            parent: dict[str, Any] = {}
            for name, path in parent_paths.items():
                inherited = value_at_path(group, path, self._MISSING)
                if inherited is self._MISSING:
                    raise SchemaMismatchError(
                        f"{self.config.company_id}: nested parent path {path!r} missing in group {group_index}"
                    )
                parent[name] = inherited
            for child_index, child in enumerate(children):
                if not isinstance(child, dict):
                    raise SchemaMismatchError(
                        f"{self.config.company_id}: nested child {group_index}/{child_index} is not an object"
                    )
                records.append({"item": child, "parent": parent})
        return records

    def _items(self, response: Any) -> tuple[list[Any], bool]:
        nested = self._nested_items(response)
        if nested is not None:
            return nested, True
        items = value_at_path(response, self.config.options.get("items_path"))
        if not isinstance(items, list):
            raise SchemaMismatchError(f"{self.config.company_id}: JSON item path is not a list")
        return items, False

    def list_jobs(self, company_config):
        o = self.config.options
        pagination = o.get("pagination", {})
        page, refs, expected, max_pages = pagination.get("start", 1), [], None, None
        nested_feed = "nested_items" in o
        completed = False
        for _ in range(pagination.get("safety_max_pages", 1000) if pagination else 1):
            params = dict(o.get("query_params", {}))
            if pagination:
                params[pagination.get("page_param", "page")] = page
            response = self._request(o.get("method", "GET").upper(), self.config.endpoint_url, params=params, json=o.get("body") if "body" in o else None).json()
            items, _ = self._items(response)
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
                locations = self._field(item, "locations", [])
                if isinstance(locations, dict):
                    locations = list(locations.values())
                mode = work_mode_from_explicit(self._field(item, "work_mode"), locations)
                refs.append(JobReference(
                    self.config.company_id,
                    str(external_id) if external_id is not None else None,
                    str(url),
                    {"item": item},
                    ListingFacts(
                        title=clean_text(title),
                        locations=tuple(locations_from_raw(locations)),
                        work_mode=mode if mode is not WorkMode.UNSPECIFIED else None,
                        department=clean_text(self._field(item, "department")),
                        employment_type=clean_text(self._field(item, "employment_type")),
                        date_posted=parse_date(self._field(item, "date_posted")),
                        source_updated_at=parse_datetime(self._field(item, "source_updated_at")),
                    ),
                ))
            if max_pages is None and expected is not None and items:
                max_pages = math.ceil(expected / len(items))
            if not pagination or not items or (max_pages is not None and page >= max_pages):
                completed = True
                break
            page += pagination.get("step", 1)
        if not completed:
            raise PaginationCapError(
                f"{self.config.company_id}: JSON pagination safety ceiling reached before completeness was proven"
            )
        if expected == 0:
            raise ConfirmedEmptyInventoryError(f"{self.config.company_id}: source explicitly reports zero jobs")
        if expected is not None and len(refs) != expected:
            raise CountMismatchError(f"{self.config.company_id}: expected {expected} JSON jobs, extracted {len(refs)}")
        if not refs:
            raise UnvalidatedEmptyInventoryError(f"{self.config.company_id}: no jobs and no validated zero count")
        if nested_feed:
            seen: set[tuple[str, str]] = set()
            for reference in refs:
                identity = (
                    ("external", reference.external_job_id)
                    if reference.external_job_id is not None
                    else ("url", reference.canonical_url)
                )
                if identity in seen:
                    raise SchemaMismatchError(
                        f"{self.config.company_id}: duplicate nested job identity {identity[1]}"
                    )
                seen.add(identity)
            refs.sort(key=lambda reference: (
                "0" if reference.external_job_id is not None else "1",
                reference.external_job_id or reference.canonical_url,
            ))
        return refs

    def fetch_job(self, ref):
        item = ref.metadata["item"]
        values = self._field(item, "locations", [])
        if isinstance(values, dict):
            values = list(values.values())
        title = clean_text(self._field(item, "title"))
        description = clean_text(self._field(item, "description"))
        detail_selectors = self.config.options.get("detail_selectors")
        if detail_selectors is not None:
            if not isinstance(detail_selectors, dict) or not detail_selectors.get("description"):
                raise SchemaMismatchError(
                    f"{self.config.company_id}: JSON detail_selectors requires description"
                )
            soup = BeautifulSoup(self._request("GET", ref.canonical_url).text, "html.parser")
            description_node = soup.select_one(detail_selectors["description"])
            if description_node is None:
                raise SchemaMismatchError(
                    f"{self.config.company_id}: configured JSON detail description selector missing"
                )
            description = clean_text(str(description_node))
            if detail_selectors.get("title"):
                title_node = soup.select_one(detail_selectors["title"])
                if title_node is None:
                    raise SchemaMismatchError(
                        f"{self.config.company_id}: configured JSON detail title selector missing"
                    )
                title = clean_text(title_node.get_text(" ", strip=True))
        return NormalizedJob(self.config.company_id, self.config.company_name, ref.external_job_id, title, locations_from_raw(values), work_mode_from_explicit(self._field(item, "work_mode"), values), ref.canonical_url, description, parse_date(self._field(item, "date_posted")), parse_date(self._field(item, "valid_through")), clean_text(self._field(item, "employment_type")), clean_text(self._field(item, "department")), self.source, utc_now())
