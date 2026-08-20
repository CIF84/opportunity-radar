from datetime import datetime, timezone

import pytest

from opportunity_radar.models import JobLocation, NormalizedJob, WorkMode


def test_normalized_job_serializes_structured_locations():
    job = NormalizedJob(
        company_id="acme",
        company_name="Acme",
        external_job_id="R1",
        title="Analyst",
        locations=[JobLocation(raw="Praha", city="Prague", country="Czechia")],
        work_mode=WorkMode.HYBRID,
        canonical_url="https://example.test/R1",
        description=None,
        date_posted=None,
        valid_through=None,
        employment_type=None,
        department=None,
        source="fixture",
        retrieved_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )
    value = job.to_dict()
    assert value["locations"] == [{"raw": "Praha", "city": "Prague", "region": None, "country": "Czechia"}]
    assert value["work_mode"] == "hybrid"


def test_raw_location_cannot_be_empty():
    with pytest.raises(ValueError):
        JobLocation(raw=" ")

