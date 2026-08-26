from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any


class WorkMode(str, Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNSPECIFIED = "unspecified"


@dataclass(frozen=True)
class JobLocation:
    raw: str
    city: str | None = None
    region: str | None = None
    country: str | None = None

    def __post_init__(self) -> None:
        if not self.raw.strip():
            raise ValueError("JobLocation.raw must not be empty")


@dataclass(frozen=True)
class ListingFacts:
    """Optional normalized evidence available before detail retrieval."""

    title: str | None = None
    locations: tuple[JobLocation, ...] = ()
    work_mode: WorkMode | None = None
    department: str | None = None
    employment_type: str | None = None
    date_posted: date | None = None
    source_updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        updated = self.source_updated_at
        if updated and updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return {
            "title": self.title,
            "locations": [asdict(item) for item in self.locations],
            "work_mode": self.work_mode.value if self.work_mode else None,
            "department": self.department,
            "employment_type": self.employment_type,
            "date_posted": self.date_posted.isoformat() if self.date_posted else None,
            "source_updated_at": updated.astimezone(timezone.utc).isoformat() if updated else None,
        }


@dataclass(frozen=True)
class JobReference:
    company_id: str
    external_job_id: str | None
    canonical_url: str
    metadata: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    listing_facts: ListingFacts = field(default_factory=ListingFacts)


@dataclass(frozen=True)
class NormalizedJob:
    company_id: str
    company_name: str
    external_job_id: str | None
    title: str
    locations: list[JobLocation]
    work_mode: WorkMode
    canonical_url: str
    description: str | None
    date_posted: date | None
    valid_through: date | None
    employment_type: str | None
    department: str | None
    source: str
    retrieved_at: datetime

    def __post_init__(self) -> None:
        if not self.company_id or not self.company_name or not self.title:
            raise ValueError("company_id, company_name and title are required")
        if not self.canonical_url.startswith(("http://", "https://")):
            raise ValueError("canonical_url must be absolute")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["work_mode"] = self.work_mode.value
        value["date_posted"] = self.date_posted.isoformat() if self.date_posted else None
        value["valid_through"] = self.valid_through.isoformat() if self.valid_through else None
        value["retrieved_at"] = self.retrieved_at.astimezone(timezone.utc).isoformat()
        return value


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
