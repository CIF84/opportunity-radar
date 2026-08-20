from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def json_ld_objects(soup: BeautifulSoup) -> Iterable[dict[str, Any]]:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            for candidate in graph if isinstance(graph, list) else [item]:
                if isinstance(candidate, dict):
                    yield candidate


def jobposting_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    return [item for item in json_ld_objects(soup) if item.get("@type") == "JobPosting"]


def value_text(node: Tag | None, attr: str | None = None) -> str | None:
    if node is None:
        return None
    value = node.get(attr) if attr else node.get_text(" ", strip=True)
    return str(value).strip() if value else None


def selector_refs(soup: BeautifulSoup, base_url: str, selectors: dict[str, str]) -> list[dict[str, str | None]]:
    container_selector = selectors.get("job_container")
    if not container_selector:
        return []
    results = []
    for container in soup.select(container_selector):
        link = container.select_one(selectors.get("url", "a[href]"))
        href = value_text(link, "href")
        title = value_text(container.select_one(selectors["title"])) if selectors.get("title") else value_text(link)
        location = value_text(container.select_one(selectors["location"])) if selectors.get("location") else None
        external_id = None
        if selectors.get("external_id"):
            external_id = value_text(container.select_one(selectors["external_id"]))
        if href and title:
            results.append(
                {"url": urljoin(base_url, href), "title": title, "location": location, "external_id": external_id}
            )
    return results


def id_from_url(url: str) -> str | None:
    match = re.search(r"(?:/|=)([A-Za-z]*\d{4,})(?:[/?#-]|$)", url)
    return match.group(1) if match else None
