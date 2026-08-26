from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.change_detection import canonical_location, canonical_text, stable_json
from opportunity_radar.models import JobLocation, ListingFacts, WorkMode


ISO_ALPHA2_CODES = frozenset("""AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW""".split())
MULTI_LOCATION_SUMMARY = re.compile(r"\+\s*\d+\s+more", re.I)


class ScopeConfigurationError(ValueError):
    pass


class SelectionDecision(str, Enum):
    SELECT_IN_SCOPE = "SELECT_IN_SCOPE"
    SELECT_GEOGRAPHY_UNKNOWN = "SELECT_GEOGRAPHY_UNKNOWN"
    SELECT_REMOTE_ELIGIBILITY_UNKNOWN = "SELECT_REMOTE_ELIGIBILITY_UNKNOWN"
    SKIP_EXPLICITLY_OUT_OF_SCOPE = "SKIP_EXPLICITLY_OUT_OF_SCOPE"


@dataclass(frozen=True)
class MarketScope:
    version: int
    country_aliases: frozenset[str]
    city_aliases: frozenset[str]
    remote_region_aliases: frozenset[str]
    incompatible_country_aliases: frozenset[str]
    retain_unknown_geography: bool
    retain_remote_unknown_eligibility: bool


@dataclass(frozen=True)
class DetailSelection:
    decision: SelectionDecision
    reason: str

    @property
    def selected(self) -> bool:
        return self.decision is not SelectionDecision.SKIP_EXPLICITLY_OUT_OF_SCOPE


def _normalized(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    ).strip()


def _aliases(values: Any, field: str) -> frozenset[str]:
    if not isinstance(values, list) or not all(isinstance(item, str) and item.strip() for item in values):
        raise ScopeConfigurationError(f"{field} must be a non-empty string list")
    return frozenset(_normalized(item) for item in values)


def load_market_scope(path: str | Path) -> MarketScope:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required = {
        "scope_version", "compatible_country_aliases", "compatible_city_aliases",
        "compatible_remote_region_aliases", "explicit_incompatible_country_aliases", "retain_unknown_geography",
        "retain_remote_unknown_eligibility",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise ScopeConfigurationError("market scope has an invalid top-level schema")
    return MarketScope(
        int(raw["scope_version"]),
        _aliases(raw["compatible_country_aliases"], "compatible_country_aliases"),
        _aliases(raw["compatible_city_aliases"], "compatible_city_aliases"),
        _aliases(raw["compatible_remote_region_aliases"], "compatible_remote_region_aliases"),
        _aliases(raw["explicit_incompatible_country_aliases"], "explicit_incompatible_country_aliases"),
        bool(raw["retain_unknown_geography"]),
        bool(raw["retain_remote_unknown_eligibility"]),
    )


def listing_facts_payload(facts: ListingFacts) -> dict[str, Any]:
    updated = facts.source_updated_at
    if updated and updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return {
        "title": canonical_text(facts.title),
        "locations": [list(value) for value in sorted(set(canonical_location(item) for item in facts.locations))],
        "work_mode": facts.work_mode.value if facts.work_mode else None,
        "department": canonical_text(facts.department),
        "employment_type": canonical_text(facts.employment_type),
        "date_posted": facts.date_posted.isoformat() if facts.date_posted else None,
        "source_updated_at": updated.astimezone(timezone.utc).isoformat() if updated else None,
    }


def listing_facts_fingerprint(facts: ListingFacts) -> str:
    return hashlib.sha256(stable_json(listing_facts_payload(facts)).encode("utf-8")).hexdigest()


def _contains_alias(raw: str, aliases: frozenset[str]) -> bool:
    text = f" {_normalized(raw)} "
    return any(f" {alias} " in text for alias in aliases)


def _positional_country_code(raw: str) -> str | None:
    """Parse the country slot used by SuccessFactors without scanning arbitrary tokens."""
    if MULTI_LOCATION_SUMMARY.search(raw):
        return None
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if len(parts) >= 3 and parts[-2] in ISO_ALPHA2_CODES:
        return parts[-2]
    if len(parts) >= 2 and parts[-1] in ISO_ALPHA2_CODES:
        return parts[-1]
    if len(parts) == 2 and parts[0] in ISO_ALPHA2_CODES:
        return parts[0]
    return None


def _location_evidence(location: JobLocation, scope: MarketScope) -> str:
    if MULTI_LOCATION_SUMMARY.search(location.raw):
        return "UNKNOWN"
    country = _normalized(location.country) if location.country else None
    city = _normalized(location.city) if location.city else None
    if country:
        return "COMPATIBLE" if country in scope.country_aliases else "INCOMPATIBLE"
    if city and city in scope.city_aliases:
        return "COMPATIBLE"
    positional_code = _positional_country_code(location.raw)
    if positional_code:
        return "COMPATIBLE" if positional_code == "CZ" else "INCOMPATIBLE"
    textual_country_aliases = frozenset(alias for alias in scope.country_aliases if len(alias) > 3)
    if _contains_alias(location.raw, textual_country_aliases | scope.city_aliases):
        return "COMPATIBLE"
    if _contains_alias(location.raw, scope.incompatible_country_aliases):
        return "INCOMPATIBLE"
    return "UNKNOWN"


def select_for_detail(facts: ListingFacts, scope: MarketScope) -> DetailSelection:
    evidence = [_location_evidence(item, scope) for item in facts.locations]
    remote_regions = any(
        _contains_alias(item.raw, scope.remote_region_aliases) for item in facts.locations
    )
    if "COMPATIBLE" in evidence:
        return DetailSelection(SelectionDecision.SELECT_IN_SCOPE, "LISTING_GEOGRAPHY_COMPATIBLE")
    if facts.work_mode is WorkMode.REMOTE:
        if remote_regions:
            return DetailSelection(SelectionDecision.SELECT_IN_SCOPE, "REMOTE_REGION_COMPATIBLE")
        if scope.retain_remote_unknown_eligibility:
            return DetailSelection(
                SelectionDecision.SELECT_REMOTE_ELIGIBILITY_UNKNOWN,
                "REMOTE_GEOGRAPHIC_ELIGIBILITY_NOT_PROVEN_INCOMPATIBLE",
            )
    if not evidence or "UNKNOWN" in evidence:
        if not scope.retain_unknown_geography:
            raise ScopeConfigurationError("the bounded experiment requires unknown geography retention")
        return DetailSelection(
            SelectionDecision.SELECT_GEOGRAPHY_UNKNOWN,
            "LISTING_GEOGRAPHY_MISSING_OR_UNPARSED",
        )
    return DetailSelection(
        SelectionDecision.SKIP_EXPLICITLY_OUT_OF_SCOPE,
        "ALL_LISTING_LOCATIONS_EXPLICITLY_INCOMPATIBLE",
    )


def listing_evidence_counts(facts: ListingFacts, scope: MarketScope) -> Counter:
    result = Counter()
    if facts.title:
        result["listing_title_available"] = 1
    if facts.locations:
        result["listing_location_available"] = 1
    if any(item.country for item in facts.locations):
        result["structured_country_available"] = 1
    evidence = [_location_evidence(item, scope) for item in facts.locations]
    if "COMPATIBLE" in evidence:
        result["explicit_czech"] = 1
    if facts.work_mode is WorkMode.REMOTE and any(
        _contains_alias(item.raw, scope.remote_region_aliases) for item in facts.locations
    ):
        result["explicit_compatible_remote"] = 1
    if any(
        not item.country and _location_evidence(item, scope) == "UNKNOWN"
        for item in facts.locations
    ):
        result["raw_unparsed_geography"] = 1
    return result
