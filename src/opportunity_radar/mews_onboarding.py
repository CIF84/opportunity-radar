from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.config import CompanyConfig
from opportunity_radar.models import JobReference
from opportunity_radar.scope_selection import MarketScope, listing_facts_fingerprint, select_for_detail


EXPERIMENT_TYPE = "DECLARATIVE_NESTED_FEED_EXTENSION_AND_ONBOARDING"


class MewsOnboardingError(ValueError):
    pass


@dataclass(frozen=True)
class MewsOnboardingConfig:
    raw: dict[str, Any]
    fingerprint: str

    @property
    def company(self) -> CompanyConfig:
        return CompanyConfig.from_dict(self.raw["source"])


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_mews_onboarding_config(path: str | Path) -> MewsOnboardingConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required = {
        "schema_version", "experiment_id", "experiment_type", "specification",
        "companies_path", "database_path", "market_scope_path",
        "role_audit_config_path", "source", "safety", "historical_reference",
        "privacy", "outputs",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise MewsOnboardingError("Mews onboarding config has an invalid schema")
    if raw["schema_version"] != 1 or raw["experiment_type"] != EXPERIMENT_TYPE:
        raise MewsOnboardingError("unsupported Mews onboarding experiment identity")
    safety = raw["safety"]
    if not isinstance(safety, dict) or set(safety) != {
        "connect_timeout_seconds", "read_timeout_seconds", "zero_detail_reruns",
        "max_listing_requests", "max_inventory",
    }:
        raise MewsOnboardingError("invalid Mews onboarding safety configuration")
    if safety["zero_detail_reruns"] != 2 or safety["max_listing_requests"] != 2:
        raise MewsOnboardingError("Mews zero-detail gate requires exactly two bounded listing calls")
    if raw["privacy"] != {
        "detailed_artifact": "PRIVATE_LOCAL",
        "aggregate_artifact": "REPOSITORY_SAFE",
    }:
        raise MewsOnboardingError("invalid Mews onboarding privacy boundary")
    config = MewsOnboardingConfig(raw, hashlib.sha256(_stable_json(raw).encode()).hexdigest())
    company = config.company
    if company.company_id != "mews" or company.adapter != "json_feed":
        raise MewsOnboardingError("SPEC-016 source must be the declarative Mews JSON feed")
    if "nested_items" not in company.options:
        raise MewsOnboardingError("SPEC-016 source must configure nested_items")
    return config


def reference_signature(references: list[JobReference]) -> list[dict[str, Any]]:
    return [
        {
            "external_job_id": reference.external_job_id,
            "canonical_url": reference.canonical_url,
            "listing_facts_fingerprint": listing_facts_fingerprint(reference.listing_facts),
        }
        for reference in references
    ]


def zero_detail_summary(
    first: list[JobReference],
    second: list[JobReference],
    market_scope: MarketScope,
) -> dict[str, Any]:
    first_signature = reference_signature(first)
    second_signature = reference_signature(second)
    if first_signature != second_signature:
        raise MewsOnboardingError("Mews zero-detail reruns are not deterministic")
    if not first:
        raise MewsOnboardingError("Mews inventory is empty without confirmed-zero evidence")
    ids = [item.external_job_id for item in first]
    urls = [item.canonical_url for item in first]
    if any(not identity for identity in ids) or len(ids) != len(set(ids)):
        raise MewsOnboardingError("Mews external identities are missing or duplicated")
    if len(urls) != len(set(urls)):
        raise MewsOnboardingError("Mews canonical URLs are duplicated")
    if any(not item.listing_facts.title or not item.canonical_url.startswith("https://") for item in first):
        raise MewsOnboardingError("Mews title or canonical URL evidence is invalid")
    decisions: dict[str, int] = {}
    for reference in first:
        decision = select_for_detail(reference.listing_facts, market_scope).decision.value
        decisions[decision] = decisions.get(decision, 0) + 1
    return {
        "inventory": len(first),
        "unique_external_ids": len(set(ids)),
        "unique_canonical_urls": len(set(urls)),
        "deterministic_rerun_equal": True,
        "detail_calls": 0,
        "phase2_writes": 0,
        "market_scope_counts": decisions,
    }
