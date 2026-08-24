from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from html import unescape
from typing import Any

from bs4 import BeautifulSoup

from opportunity_radar.models import JobLocation, NormalizedJob
from opportunity_radar.state_models import Change


MATERIAL_FIELDS = (
    "title", "locations", "work_mode", "employment_type", "department", "description"
)
EVENT_TYPES = {
    "title": "TITLE_CHANGED",
    "locations": "LOCATION_CHANGED",
    "work_mode": "WORK_MODE_CHANGED",
    "employment_type": "EMPLOYMENT_TYPE_CHANGED",
    "department": "DEPARTMENT_CHANGED",
    "description": "DESCRIPTION_CHANGED",
}


def canonical_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = BeautifulSoup(unescape(str(value)), "html.parser").get_text(" ")
    text = unicodedata.normalize("NFKC", text).replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def canonical_location(location: JobLocation) -> tuple[str, str, str, str]:
    return tuple(canonical_text(value) or "" for value in (
        location.raw, location.city, location.region, location.country
    ))


def material(job: NormalizedJob) -> dict[str, Any]:
    return {
        "title": canonical_text(job.title),
        "locations": [list(item) for item in sorted(set(canonical_location(item) for item in job.locations))],
        "work_mode": job.work_mode.value,
        "employment_type": canonical_text(job.employment_type),
        "department": canonical_text(job.department),
        "description": canonical_text(job.description),
    }


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(job: NormalizedJob) -> str:
    return hashlib.sha256(stable_json(material(job)).encode("utf-8")).hexdigest()


def compare_material(old: dict[str, Any], new: dict[str, Any]) -> list[Change]:
    changes = []
    for field in MATERIAL_FIELDS:
        if old.get(field) != new.get(field):
            changes.append(Change(EVENT_TYPES[field], old.get(field), new.get(field)))
    return changes


def snapshot(job: NormalizedJob) -> str:
    return stable_json(job.to_dict())
