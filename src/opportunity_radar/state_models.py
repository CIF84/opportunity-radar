from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from opportunity_radar.models import JobReference, NormalizedJob


@dataclass(frozen=True)
class DetailObservation:
    reference: JobReference
    job: NormalizedJob


@dataclass
class SourceOutcome:
    company_id: str
    company_name: str
    adapter: str
    status: str
    observed_at: datetime
    references: list[JobReference] = field(default_factory=list)
    details: list[DetailObservation] = field(default_factory=list)
    inventory_complete: bool = False
    selected_details_complete: bool = False
    expected_count: int | None = None
    detail_failure_count: int = 0
    error_type: str | None = None
    error_message: str | None = None
    selected_for_detail_count: int = 0
    intentionally_skipped_count: int = 0
    network_detail_request_count: int = 0
    reused_detail_count: int = 0
    details_to_fetch_count: int = 0

    @property
    def observed_count(self) -> int:
        return len(self.references)

    @property
    def inventory_count(self) -> int:
        return len(self.references)

    @property
    def detail_success_count(self) -> int:
        return len(self.details)

    @property
    def details_complete(self) -> bool:
        """Compatibility alias for the persisted Phase 2 column name."""
        return self.selected_details_complete


@dataclass(frozen=True)
class Change:
    event_type: str
    old: object
    new: object
