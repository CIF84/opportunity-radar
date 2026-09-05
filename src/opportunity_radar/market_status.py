from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

import yaml

from opportunity_radar.phase3_config import Phase3ConfigurationError, stable_json
from opportunity_radar.phase3_models import CandidateProfile, SemanticJobInput


EVALUATOR_VERSION = "phase4-current-candidate-market-v2"


class CurrentCandidateMarketStatus(str, Enum):
    IN_SCOPE = "IN_SCOPE"
    UNCERTAIN = "UNCERTAIN"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class MarketReasonEffect(str, Enum):
    SUPPORTS_IN_SCOPE = "SUPPORTS_IN_SCOPE"
    SUPPORTS_UNCERTAIN = "SUPPORTS_UNCERTAIN"
    SUPPORTS_OUT_OF_SCOPE = "SUPPORTS_OUT_OF_SCOPE"


class MarketReasonCode(str, Enum):
    ACCEPTED_LOCATION_COMPATIBLE = "ACCEPTED_LOCATION_COMPATIBLE"
    FOREIGN_ONSITE_INCOMPATIBLE = "FOREIGN_ONSITE_INCOMPATIBLE"
    EXPLICIT_FOREIGN_REGION_INCOMPATIBLE = "EXPLICIT_FOREIGN_REGION_INCOMPATIBLE"
    REMOTE_RESIDENCE_CONFIRMED = "REMOTE_RESIDENCE_CONFIRMED"
    REMOTE_COUNTRY_RESTRICTED = "REMOTE_COUNTRY_RESTRICTED"
    REMOTE_ELIGIBILITY_UNKNOWN = "REMOTE_ELIGIBILITY_UNKNOWN"
    WORKING_HOURS_COMPATIBLE = "WORKING_HOURS_COMPATIBLE"
    WORKING_HOURS_INCOMPATIBLE = "WORKING_HOURS_INCOMPATIBLE"
    WORKING_HOURS_UNKNOWN = "WORKING_HOURS_UNKNOWN"
    WORK_AUTHORIZATION_COMPATIBLE = "WORK_AUTHORIZATION_COMPATIBLE"
    WORK_AUTHORIZATION_INCOMPATIBLE = "WORK_AUTHORIZATION_INCOMPATIBLE"
    WORK_AUTHORIZATION_UNKNOWN = "WORK_AUTHORIZATION_UNKNOWN"
    REQUIRED_LANGUAGE_SUPPORTED = "REQUIRED_LANGUAGE_SUPPORTED"
    REQUIRED_LANGUAGE_INCOMPATIBLE = "REQUIRED_LANGUAGE_INCOMPATIBLE"
    REQUIRED_LANGUAGE_UNKNOWN = "REQUIRED_LANGUAGE_UNKNOWN"
    INCOMPLETE_MULTI_LOCATION = "INCOMPLETE_MULTI_LOCATION"
    GEOGRAPHY_UNKNOWN = "GEOGRAPHY_UNKNOWN"
    WORK_MODE_UNKNOWN = "WORK_MODE_UNKNOWN"


@dataclass(frozen=True)
class MarketEvidence:
    evidence_id: str
    kind: str
    source_field: str
    raw_value: str
    normalized_value: str | None = None


@dataclass(frozen=True)
class MarketReason:
    code: MarketReasonCode
    effect: MarketReasonEffect
    evidence_ids: tuple[str, ...]
    candidate_policy_evidence: str


@dataclass(frozen=True)
class CurrentCandidateMarketAssessment:
    status: CurrentCandidateMarketStatus
    reasons: tuple[MarketReason, ...]
    evidence: tuple[MarketEvidence, ...]
    evaluator_version: str
    normalization_version: str
    candidate_profile_id: str
    candidate_profile_version: int
    market_policy_version: int
    market_access_policy_fingerprint: str
    input_fingerprint: str
    assessment_fingerprint: str

    def payload(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        for reason in result["reasons"]:
            reason["code"] = reason["code"].value
            reason["effect"] = reason["effect"].value
        return result


@dataclass(frozen=True)
class MarketNormalizationRules:
    normalization_version: str
    country_aliases: dict[str, tuple[str, ...]]
    city_countries: dict[str, str]
    region_countries: dict[str, str]
    remote_scope_aliases: dict[str, tuple[str, ...]]
    incomplete_location_patterns: tuple[str, ...]
    work_mode_patterns: dict[str, tuple[str, ...]]
    remote_compatibility_patterns: tuple[str, ...]
    remote_restriction_patterns: tuple[str, ...]
    authorization_requirement_patterns: tuple[str, ...]
    language_requirement_patterns: tuple[str, ...]
    compatible_working_time_patterns: tuple[str, ...]
    incompatible_working_time_patterns: tuple[str, ...]


def _digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _text(value: Any) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).replace("\u00a0", " ")


def _search_text(value: Any) -> str:
    folded = unicodedata.normalize("NFKD", _text(value))
    return " ".join(folded.encode("ascii", "ignore").decode().casefold().split())


def _contains(text: str, value: str) -> bool:
    normalized = _search_text(value)
    return bool(normalized and re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", text))


def _compile_all(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)


def _effect_for_status(status: str) -> MarketReasonEffect:
    return {
        "IN_SCOPE": MarketReasonEffect.SUPPORTS_IN_SCOPE,
        "UNCERTAIN": MarketReasonEffect.SUPPORTS_UNCERTAIN,
        "OUT_OF_SCOPE": MarketReasonEffect.SUPPORTS_OUT_OF_SCOPE,
    }[status]


def load_market_normalization_rules(path: str | Path) -> MarketNormalizationRules:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required = {
        "normalization_version", "country_aliases", "city_countries",
        "region_countries",
        "remote_scope_aliases", "incomplete_location_patterns", "work_mode_patterns",
        "remote_compatibility_patterns", "remote_restriction_patterns",
        "authorization_requirement_patterns", "language_requirement_patterns",
        "compatible_working_time_patterns", "incompatible_working_time_patterns",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise Phase3ConfigurationError("market normalization rules have an invalid schema")
    if not isinstance(raw["normalization_version"], str) or not raw["normalization_version"]:
        raise Phase3ConfigurationError("market normalization version must be a non-empty string")
    if not isinstance(raw["city_countries"], dict) or any(
        not isinstance(city, str) or not isinstance(country, str)
        for city, country in raw["city_countries"].items()
    ):
        raise Phase3ConfigurationError("invalid market normalization section: city_countries")
    if not isinstance(raw["region_countries"], dict) or any(
        not isinstance(region, str) or not isinstance(country, str)
        for region, country in raw["region_countries"].items()
    ):
        raise Phase3ConfigurationError("invalid market normalization section: region_countries")
    if set(raw["work_mode_patterns"]) != {"onsite", "hybrid", "remote"}:
        raise Phase3ConfigurationError("market work-mode patterns must define onsite, hybrid, remote")
    for section in (
        "country_aliases", "remote_scope_aliases", "work_mode_patterns",
    ):
        if not isinstance(raw[section], dict) or any(
            not isinstance(values, list) or not values for values in raw[section].values()
        ):
            raise Phase3ConfigurationError(f"invalid market normalization section: {section}")
    for section in (
        "incomplete_location_patterns", "remote_compatibility_patterns",
        "remote_restriction_patterns", "authorization_requirement_patterns",
        "language_requirement_patterns", "compatible_working_time_patterns",
        "incompatible_working_time_patterns",
    ):
        if not isinstance(raw[section], list) or any(not isinstance(x, str) for x in raw[section]):
            raise Phase3ConfigurationError(f"invalid market normalization section: {section}")
        for pattern in raw[section]:
            re.compile(pattern.replace("{language}", "English"))
    return MarketNormalizationRules(
        normalization_version=raw["normalization_version"],
        country_aliases={key: tuple(value) for key, value in raw["country_aliases"].items()},
        city_countries=dict(raw["city_countries"]),
        region_countries=dict(raw["region_countries"]),
        remote_scope_aliases={key: tuple(value) for key, value in raw["remote_scope_aliases"].items()},
        incomplete_location_patterns=tuple(raw["incomplete_location_patterns"]),
        work_mode_patterns={key: tuple(value) for key, value in raw["work_mode_patterns"].items()},
        remote_compatibility_patterns=tuple(raw["remote_compatibility_patterns"]),
        remote_restriction_patterns=tuple(raw["remote_restriction_patterns"]),
        authorization_requirement_patterns=tuple(raw["authorization_requirement_patterns"]),
        language_requirement_patterns=tuple(raw["language_requirement_patterns"]),
        compatible_working_time_patterns=tuple(raw["compatible_working_time_patterns"]),
        incompatible_working_time_patterns=tuple(raw["incompatible_working_time_patterns"]),
    )


def _country_from_value(value: Any, rules: MarketNormalizationRules, *, structured: bool) -> str | None:
    raw = _text(value).strip()
    normalized = _search_text(raw)
    if not normalized:
        return None
    for country, aliases in rules.country_aliases.items():
        for alias in aliases:
            candidate = _search_text(alias)
            if normalized == candidate:
                return country
            # Two-letter codes are positional data, never arbitrary substrings.
            if len(candidate) <= 2 and not structured:
                continue
            if len(candidate) > 2 and _contains(normalized, candidate):
                return country
    for city, country in rules.city_countries.items():
        if _contains(normalized, city):
            return country
    # Region names are deliberately declarative and bounded. They are matched
    # as whole tokens, never as state-code-like substrings. Ambiguous region
    # names are intentionally omitted from configuration.
    for region, country in rules.region_countries.items():
        if _contains(normalized, region):
            return country
    if not structured:
        for part in re.split(r"[,;|/]", raw):
            token = re.sub(r"\+\s*\d+.*$", "", part).strip()
            if token and token != raw:
                country = _country_from_value(token, rules, structured=True)
                if country:
                    return country
    return None


def _region_country_from_value(value: Any, rules: MarketNormalizationRules) -> str | None:
    normalized = _search_text(value)
    return next(
        (
            country for region, country in rules.region_countries.items()
            if _contains(normalized, region)
        ),
        None,
    )


def _city_from_value(value: Any, rules: MarketNormalizationRules) -> str | None:
    normalized = _search_text(value)
    for city in rules.city_countries:
        if _contains(normalized, city):
            return city
    return None


def _location_matches(location: dict[str, Any], accepted: dict[str, str], rules: MarketNormalizationRules) -> bool:
    country = _country_from_value(location.get("country"), rules, structured=True)
    city = _text(location.get("city")).strip() or _city_from_value(location.get("raw"), rules)
    if country is None:
        country = _country_from_value(location.get("raw"), rules, structured=False)
    if _search_text(country) != _search_text(accepted.get("country")):
        return False
    return not accepted.get("city") or _search_text(city) == _search_text(accepted["city"])


class _EvidenceBuilder:
    def __init__(self) -> None:
        self.evidence: list[MarketEvidence] = []

    def add(self, kind: str, field: str, raw: Any, normalized: str | None = None) -> str:
        raw_value = _text(raw)
        if len(raw_value) > 500:
            raw_value = raw_value[:499] + "…"
        item = MarketEvidence(
            evidence_id=f"e{len(self.evidence) + 1}", kind=kind, source_field=field,
            raw_value=raw_value, normalized_value=normalized,
        )
        self.evidence.append(item)
        return item.evidence_id


def _effective_work_mode(job: SemanticJobInput, rules: MarketNormalizationRules) -> tuple[str, str]:
    mode = _search_text(job.work_mode)
    if mode in {"onsite", "hybrid", "remote"}:
        return mode, "work_mode"
    description = _text(job.description)
    # Hybrid is the most specific mixed arrangement and wins over incidental remote/office prose.
    if _compile_all(rules.work_mode_patterns["hybrid"], description):
        return "hybrid", "description"
    if _compile_all(rules.work_mode_patterns["onsite"], description):
        return "onsite", "description"
    if _compile_all(rules.work_mode_patterns["remote"], description):
        return "remote", "description"
    return "unspecified", "work_mode"


def _job_payload(job: SemanticJobInput) -> dict[str, Any]:
    supported_supplemental = {
        key: job.supplemental_evidence[key]
        for key in (
            "remote_geography", "work_authorization", "residency_requirements",
            "required_languages", "working_hours",
        )
        if key in job.supplemental_evidence
    }
    return {
        "title": job.title,
        "description": job.description,
        "locations": list(job.locations),
        "work_mode": job.work_mode,
        "employment_type": job.employment_type,
        "department": job.department,
        "supplemental_evidence": supported_supplemental,
    }


def evaluate_current_candidate_market(
    job: SemanticJobInput,
    candidate: CandidateProfile,
    rules: MarketNormalizationRules,
) -> CurrentCandidateMarketAssessment:
    """Pure, post-detail candidate-market assessment; it performs no I/O or routing."""
    policy = candidate.market_access_policy
    builder = _EvidenceBuilder()
    reasons: list[MarketReason] = []

    def reason(
        code: MarketReasonCode,
        effect: MarketReasonEffect,
        evidence_ids: Iterable[str],
        policy_evidence: str,
    ) -> None:
        item = MarketReason(code, effect, tuple(evidence_ids), policy_evidence)
        if item not in reasons:
            reasons.append(item)

    locations = tuple(job.locations)
    raw_locations = [_text(x.get("raw")) for x in locations if _text(x.get("raw")).strip()]
    incomplete_values = [
        value for value in raw_locations
        if _compile_all(rules.incomplete_location_patterns, value)
    ]
    incomplete = bool(incomplete_values)

    countries: list[tuple[str, str]] = []
    explicit_region_evidence_ids: list[str] = []
    for index, location in enumerate(locations):
        raw = location.get("country") or location.get("raw") or location.get("city")
        country = _country_from_value(location.get("country"), rules, structured=True)
        if country is None:
            country = _country_from_value(location.get("raw"), rules, structured=False)
        if country is None:
            country = _country_from_value(location.get("city"), rules, structured=True)
        if country:
            evidence_id = builder.add("location", f"locations[{index}]", raw, country)
            countries.append((country, evidence_id))
            if _region_country_from_value(location.get("raw"), rules) == country:
                explicit_region_evidence_ids.append(evidence_id)

    accepted_locations = policy.onsite_hybrid["accepted_locations"]
    accepted_matches = [
        index for index, location in enumerate(locations)
        if any(_location_matches(location, accepted, rules) for accepted in accepted_locations)
    ]
    mode, mode_source = _effective_work_mode(job, rules)
    mode_id = builder.add("work_mode", mode_source, job.work_mode if mode_source == "work_mode" else job.description, mode)

    supported_supplemental = _job_payload(job)["supplemental_evidence"]
    all_text = "\n".join(
        [_text(job.title), _text(job.description)]
        + [_text(value) for location in locations for value in location.values() if value]
        + [_text(value) for value in supported_supplemental.values()]
    )
    search = _search_text(all_text)
    countries_in_text = [
        country
        for country, aliases in rules.country_aliases.items()
        if any(
            (len(_search_text(alias)) > 2 or "." in alias)
            and _contains(search, alias)
            for alias in aliases
        )
    ]

    # An explicit compatible member can resolve an incomplete location summary;
    # otherwise omitted members remain material uncertainty.
    if incomplete and not (mode in {"onsite", "hybrid"} and accepted_matches):
        ids = [builder.add("location", "locations.raw", value) for value in incomplete_values]
        reason(
            MarketReasonCode.INCOMPLETE_MULTI_LOCATION,
            MarketReasonEffect.SUPPORTS_UNCERTAIN,
            ids,
            "Incomplete location evidence is retained as uncertainty.",
        )

    # Explicit work-authorization requirements are evaluated only when present.
    if _compile_all(rules.authorization_requirement_patterns, all_text):
        jurisdiction = next(iter(countries_in_text), None)
        if jurisdiction is None and countries:
            jurisdiction = countries[0][0]
        auth_id = builder.add("work_authorization", "description", job.description, jurisdiction)
        auth_status = policy.work_access_status(jurisdiction or "")
        if auth_status is None:
            auth_status = policy.work_access_status("foreign_default")
        if auth_status == "INCOMPATIBLE":
            reason(MarketReasonCode.WORK_AUTHORIZATION_INCOMPATIBLE, MarketReasonEffect.SUPPORTS_OUT_OF_SCOPE, (auth_id,), f"work_access[{jurisdiction or 'foreign_default'}]=INCOMPATIBLE")
        elif auth_status == "CONFIRMED":
            reason(MarketReasonCode.WORK_AUTHORIZATION_COMPATIBLE, MarketReasonEffect.SUPPORTS_IN_SCOPE, (auth_id,), f"work_access[{jurisdiction}]=CONFIRMED")
        else:
            reason(MarketReasonCode.WORK_AUTHORIZATION_UNKNOWN, MarketReasonEffect.SUPPORTS_UNCERTAIN, (auth_id,), f"work_access[{jurisdiction or 'foreign_default'}] is UNKNOWN or omitted")

    # Required-language matching is limited to languages represented by candidate policy.
    for language, details in policy.languages.items():
        patterns = [pattern.replace("{language}", re.escape(language)) for pattern in rules.language_requirement_patterns]
        matches = [match.group(0) for pattern in patterns for match in re.finditer(pattern, all_text, flags=re.IGNORECASE | re.DOTALL)]
        if not matches:
            continue
        language_id = builder.add("required_language", "description", matches[0], language)
        sentence = next((part for part in re.split(r"(?<=[.!?])\s+", all_text) if _contains(_search_text(part), language) and any(re.search(pattern, part, re.IGNORECASE) for pattern in patterns)), matches[0])
        alternatives = [name for name in policy.languages if name != language and _contains(_search_text(sentence), name)]
        supported_alternative = any(policy.language_support(name) in {"NATIVE_PROFESSIONAL", "PROFESSIONAL", "COMPREHENSION_ONLY"} for name in alternatives)
        support = str(details["support"])
        if support == "NONE" and not supported_alternative:
            reason(MarketReasonCode.REQUIRED_LANGUAGE_INCOMPATIBLE, MarketReasonEffect.SUPPORTS_OUT_OF_SCOPE, (language_id,), f"languages[{language}].support=NONE")
        elif support == "UNKNOWN":
            reason(MarketReasonCode.REQUIRED_LANGUAGE_UNKNOWN, MarketReasonEffect.SUPPORTS_UNCERTAIN, (language_id,), f"languages[{language}].support=UNKNOWN")
        else:
            reason(MarketReasonCode.REQUIRED_LANGUAGE_SUPPORTED, MarketReasonEffect.SUPPORTS_IN_SCOPE, (language_id,), f"languages[{language}].support={support}")

    if mode in {"onsite", "hybrid"}:
        if accepted_matches:
            ids = [builder.add("accepted_location", f"locations[{index}]", locations[index].get("raw") or locations[index], "accepted") for index in accepted_matches]
            reason(MarketReasonCode.ACCEPTED_LOCATION_COMPATIBLE, MarketReasonEffect.SUPPORTS_IN_SCOPE, ids + [mode_id], "Location matches onsite_hybrid.accepted_locations")
        elif countries and not incomplete:
            effect = MarketReasonEffect.SUPPORTS_OUT_OF_SCOPE if policy.onsite_hybrid["outside_accepted_locations"] == "OUT_OF_SCOPE" else MarketReasonEffect.SUPPORTS_UNCERTAIN
            reason(MarketReasonCode.FOREIGN_ONSITE_INCOMPATIBLE, effect, [evidence_id for _, evidence_id in countries] + [mode_id], f"onsite_hybrid.outside_accepted_locations={policy.onsite_hybrid['outside_accepted_locations']}; relocation.normal_shortlist={policy.relocation['normal_shortlist']}")
        elif not incomplete:
            reason(MarketReasonCode.GEOGRAPHY_UNKNOWN, MarketReasonEffect.SUPPORTS_UNCERTAIN, (mode_id,), "Onsite/hybrid geography cannot be established")
    elif mode == "remote":
        residence = str(policy.remote["residence_country"])
        residence_mentioned = _contains(search, residence)
        scope_labels = [
            label
            for label, aliases in rules.remote_scope_aliases.items()
            if label in policy.remote["compatible_scope_labels"]
            and any(_contains(search, alias) for alias in aliases)
        ]
        scope_is_sufficient = bool(scope_labels) and not policy.remote[
            "require_confirmed_residence_compatibility"
        ]
        restriction = _compile_all(rules.remote_restriction_patterns, all_text)
        foreign_countries = [(country, evidence_id) for country, evidence_id in countries if _search_text(country) != _search_text(residence)]
        explicit_remote_location = any(
            _contains(_search_text(raw), "remote")
            and _country_from_value(raw, rules, structured=False) is not None
            for raw in raw_locations
        )
        restricted_country = next(
            (country for country in countries_in_text if _search_text(country) != _search_text(residence)),
            foreign_countries[0][0] if foreign_countries else None,
        )
        if (restriction or explicit_remote_location) and restricted_country:
            restriction_id = builder.add("remote_restriction", "description_or_location", all_text, restricted_country)
            related = [evidence_id for country, evidence_id in foreign_countries if country == restricted_country]
            reason(MarketReasonCode.REMOTE_COUNTRY_RESTRICTED, _effect_for_status(policy.remote["explicit_foreign_restriction"]), (restriction_id, *related), f"remote.explicit_foreign_restriction={policy.remote['explicit_foreign_restriction']}")
        elif (
            residence_mentioned
            and _compile_all(rules.remote_compatibility_patterns, all_text)
        ) or scope_is_sufficient:
            normalized_remote = residence if residence_mentioned else scope_labels[0]
            remote_id = builder.add(
                "remote_compatibility", "description_or_location", all_text,
                normalized_remote,
            )
            reason(MarketReasonCode.REMOTE_RESIDENCE_CONFIRMED, _effect_for_status(policy.remote["confirmed_compatible"]), (remote_id,), f"remote.confirmed_compatible={policy.remote['confirmed_compatible']}")
        else:
            remote_id = builder.add("remote_eligibility", "description_or_location", all_text, None)
            reason(MarketReasonCode.REMOTE_ELIGIBILITY_UNKNOWN, _effect_for_status(policy.remote["employment_access_unspecified"]), (remote_id,), f"remote.employment_access_unspecified={policy.remote['employment_access_unspecified']}")

        if _compile_all(rules.incompatible_working_time_patterns, all_text):
            hours_id = builder.add("working_hours", "description", job.description, "incompatible")
            reason(MarketReasonCode.WORKING_HOURS_INCOMPATIBLE, _effect_for_status(policy.remote["incompatible_working_hours"]), (hours_id,), f"remote.incompatible_working_hours={policy.remote['incompatible_working_hours']}")
        elif _compile_all(rules.compatible_working_time_patterns, all_text):
            hours_id = builder.add("working_hours", "description", job.description, "EUROPEAN_COMPATIBLE")
            effect = (
                MarketReasonEffect.SUPPORTS_IN_SCOPE
                if "EUROPEAN_COMPATIBLE" in policy.remote["compatible_working_time_regions"]
                else MarketReasonEffect.SUPPORTS_UNCERTAIN
            )
            reason(MarketReasonCode.WORKING_HOURS_COMPATIBLE, effect, (hours_id,), f"compatible_working_time_regions={policy.remote['compatible_working_time_regions']}")
        elif any(x.code == MarketReasonCode.REMOTE_RESIDENCE_CONFIRMED for x in reasons):
            hours_id = builder.add("working_hours", "description", job.description, None)
            reason(MarketReasonCode.WORKING_HOURS_UNKNOWN, _effect_for_status(policy.remote["working_hours_unspecified"]), (hours_id,), f"remote.working_hours_unspecified={policy.remote['working_hours_unspecified']}")
    else:
        reason(MarketReasonCode.WORK_MODE_UNKNOWN, MarketReasonEffect.SUPPORTS_UNCERTAIN, (mode_id,), "Work mode cannot be established")
        if explicit_region_evidence_ids and not incomplete and not accepted_matches:
            effect = MarketReasonEffect.SUPPORTS_OUT_OF_SCOPE if policy.onsite_hybrid["outside_accepted_locations"] == "OUT_OF_SCOPE" else MarketReasonEffect.SUPPORTS_UNCERTAIN
            reason(
                MarketReasonCode.EXPLICIT_FOREIGN_REGION_INCOMPATIBLE,
                effect,
                explicit_region_evidence_ids + [mode_id],
                "A complete explicit foreign region location has no remote evidence; "
                f"onsite_hybrid.outside_accepted_locations={policy.onsite_hybrid['outside_accepted_locations']}; "
                f"relocation.normal_shortlist={policy.relocation['normal_shortlist']}",
            )
        elif not countries:
            reason(MarketReasonCode.GEOGRAPHY_UNKNOWN, MarketReasonEffect.SUPPORTS_UNCERTAIN, (mode_id,), "Geography cannot be established")

    effects = {item.effect for item in reasons}
    if MarketReasonEffect.SUPPORTS_OUT_OF_SCOPE in effects:
        status = CurrentCandidateMarketStatus.OUT_OF_SCOPE
    elif MarketReasonEffect.SUPPORTS_UNCERTAIN in effects:
        status = CurrentCandidateMarketStatus.UNCERTAIN
    elif MarketReasonEffect.SUPPORTS_IN_SCOPE in effects:
        status = CurrentCandidateMarketStatus.IN_SCOPE
    else:
        status = CurrentCandidateMarketStatus.UNCERTAIN

    input_payload = {
        "evaluator_version": EVALUATOR_VERSION,
        "normalization_version": rules.normalization_version,
        "job": _job_payload(job),
        "candidate_profile_id": candidate.profile_id,
        "candidate_profile_version": candidate.version,
        "market_policy_version": policy.policy_version,
        "market_access_policy_fingerprint": candidate.market_access_policy_fingerprint,
    }
    input_fingerprint = _digest(input_payload)
    assessment_payload = {
        "input_fingerprint": input_fingerprint,
        "status": status.value,
        "reasons": [
            {
                "code": item.code.value,
                "effect": item.effect.value,
                "evidence_ids": item.evidence_ids,
                "candidate_policy_evidence": item.candidate_policy_evidence,
            }
            for item in reasons
        ],
        "evidence": [asdict(item) for item in builder.evidence],
    }
    return CurrentCandidateMarketAssessment(
        status=status,
        reasons=tuple(reasons),
        evidence=tuple(builder.evidence),
        evaluator_version=EVALUATOR_VERSION,
        normalization_version=rules.normalization_version,
        candidate_profile_id=candidate.profile_id,
        candidate_profile_version=candidate.version,
        market_policy_version=policy.policy_version,
        market_access_policy_fingerprint=candidate.market_access_policy_fingerprint,
        input_fingerprint=input_fingerprint,
        assessment_fingerprint=_digest(assessment_payload),
    )
