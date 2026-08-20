from __future__ import annotations

import re
from html import unescape
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from opportunity_radar.config import CompanyConfig
from opportunity_radar.models import JobLocation, JobReference, NormalizedJob, WorkMode


class AdapterError(RuntimeError):
    pass


class SourceRequestError(AdapterError):
    pass


class ExtractionError(AdapterError):
    pass


class EmptyInventoryError(ExtractionError):
    pass


class SchemaMismatchError(ExtractionError):
    pass


class CountMismatchError(ExtractionError):
    pass


def value_at_path(value: Any, path: str | None, default: Any = None) -> Any:
    if not path:
        return value
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


class JobSourceAdapter(ABC):
    source = "unknown"

    def __init__(self, config: CompanyConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        if session is None:
            retry = Retry(
                total=2,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504, 520),
                allowed_methods=frozenset({"GET", "POST"}),
            )
            self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.setdefault(
            "User-Agent", "OpportunityRadarFeasibilitySpike/0.1 (+public vacancy ingestion)"
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            raise SourceRequestError(f"{method} {url}: {exc}") from exc

    @abstractmethod
    def list_jobs(self, company_config: CompanyConfig) -> list[JobReference]:
        raise NotImplementedError

    @abstractmethod
    def fetch_job(self, job_reference: JobReference) -> NormalizedJob:
        raise NotImplementedError


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", BeautifulSoup(unescape(str(value)), "html.parser").get_text(" ")).strip()
    return cleaned or None


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for candidate in (text, text[:10]):
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    for fmt in ("%b %d, %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def work_mode_from_explicit(*values: Any) -> WorkMode:
    text = " ".join(str(v) for v in values if v).lower()
    if re.search(r"\bhybrid\b", text):
        return WorkMode.HYBRID
    if re.search(r"\b(remote|telecommut\w*|home[- ]based)\b", text):
        return WorkMode.REMOTE
    if re.search(r"\b(on[- ]site|onsite)\b", text):
        return WorkMode.ONSITE
    return WorkMode.UNSPECIFIED


def locations_from_raw(values: str | Iterable[str] | None) -> list[JobLocation]:
    if not values:
        return []
    candidates = [values] if isinstance(values, str) else list(values)
    result: list[JobLocation] = []
    seen: set[str] = set()
    for value in candidates:
        raw = clean_text(value)
        if raw and raw not in seen:
            seen.add(raw)
            result.append(JobLocation(raw=raw))
    return result
