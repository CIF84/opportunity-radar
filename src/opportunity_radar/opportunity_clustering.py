from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from opportunity_radar.change_detection import canonical_text
from opportunity_radar.market_status import (
    CurrentCandidateMarketAssessment,
    CurrentCandidateMarketStatus,
    MarketReasonEffect,
    MarketReasonCode,
)
from opportunity_radar.phase3_config import stable_json
from opportunity_radar.phase3_models import CandidateProfile, EligibilityStatus


CLUSTERING_METHOD_VERSION = "phase4-high-confidence-cluster-v1"
PREFERRED_VARIANT_POLICY_VERSION = "phase4-preferred-variant-v1"
MIN_CORE_DESCRIPTION_LENGTH = 240

# These are deliberately generic boundaries between role evidence and localized
# employment/benefit copy. Text before the first sufficiently late boundary is
# retained; no employer-specific wording or fuzzy comparison is used.
_TRAILING_LOCAL_SECTION = re.compile(
    r"\b(?:we offer you|what we offer|our benefits|benefits and perks|"
    r"compensation and benefits)\b",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_COMPENSATION = re.compile(
    r"(?:(?:usd|eur|gbp)\s*)?[€£$]\s*\d[\d,]*(?:\.\d+)?"
    r"(?:\s*[–—-]\s*[€£$]?\s*\d[\d,]*(?:\.\d+)?)?"
    r"(?:\s*(?:usd|eur|gbp))?",
    re.IGNORECASE,
)


def _digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def normalize_role_title(value: str | None) -> str | None:
    text = canonical_text(value)
    if text is None:
        return None
    return unicodedata.normalize("NFKC", text).casefold()


def core_description_signature(value: str | None) -> str | None:
    """Return an exact signature of bounded, explainably normalized role evidence."""
    text = canonical_text(value)
    if text is None:
        return None
    match = _TRAILING_LOCAL_SECTION.search(text)
    if match and match.start() >= MIN_CORE_DESCRIPTION_LENGTH:
        text = text[: match.start()]
    text = _URL.sub(" <url> ", text)
    text = _COMPENSATION.sub(" <compensation> ", text)
    text = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    if len(text) < MIN_CORE_DESCRIPTION_LENGTH:
        return None
    return _digest(text)


@dataclass(frozen=True)
class ClusterMemberEvidence:
    job_instance_id: int
    company_id: str
    title: str | None
    description: str | None
    canonical_url: str
    content_fingerprint: str
    locations: tuple[dict[str, Any], ...] = ()
    work_mode: str = "unspecified"
    employment_type: str | None = None
    department: str | None = None
    lifecycle_state: str = "ACTIVE"
    detail_complete: bool = True
    source_evidence_at: str | None = None


@dataclass(frozen=True)
class ClusteringEvidence:
    signal: str
    value: str
    member_job_instance_ids: tuple[int, ...]


@dataclass(frozen=True)
class OpportunityCluster:
    cluster_id: str
    company_id: str
    canonical_role_identity: str
    member_job_instance_ids: tuple[int, ...]
    cluster_fingerprint: str
    clustering_method: str
    clustering_method_version: str
    clustering_evidence: tuple[ClusteringEvidence, ...]

    def payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VariantRankingReason:
    code: str
    detail: str
    member_job_instance_ids: tuple[int, ...]


@dataclass(frozen=True)
class PreferredVariantSelection:
    cluster_id: str
    candidate_profile_id: str
    market_access_policy_fingerprint: str
    preferred_variant_job_instance_id: int | None
    ordered_member_job_instance_ids: tuple[int, ...]
    reasons: tuple[VariantRankingReason, ...]
    selection_policy_version: str
    selection_fingerprint: str

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def _compatible_optional(values: Iterable[str | None]) -> bool:
    present = {canonical_text(value) for value in values if canonical_text(value)}
    return len(present) <= 1


def _member_identity(member: ClusterMemberEvidence) -> dict[str, Any]:
    return {
        "job_instance_id": member.job_instance_id,
        "canonical_url": member.canonical_url,
        "content_fingerprint": member.content_fingerprint,
    }


def _variant_evidence(candidates: list[ClusterMemberEvidence]) -> str | None:
    location_payloads = {
        stable_json({
            "locations": list(member.locations),
            "work_mode": member.work_mode,
        })
        for member in candidates
    }
    descriptions = {
        canonical_text(member.description)
        for member in candidates
    }
    differences = []
    if len(location_payloads) > 1:
        differences.append("LOCATION_OR_WORK_MODE")
    if len(descriptions) > 1:
        differences.append("LOCALIZED_OR_COMPENSATION_COPY")
    return "+".join(differences) or None


def cluster_opportunities(
    members: Iterable[ClusterMemberEvidence],
) -> tuple[OpportunityCluster, ...]:
    """Build conservative employer-scoped clusters using exact role evidence."""
    ordered = sorted(members, key=lambda item: (item.company_id, item.job_instance_id))
    if len({member.job_instance_id for member in ordered}) != len(ordered):
        raise ValueError("cluster input contains duplicate job_instance_id values")

    grouped: dict[tuple[str, str, str], list[ClusterMemberEvidence]] = {}
    singletons: list[ClusterMemberEvidence] = []
    for member in ordered:
        title = normalize_role_title(member.title)
        description = core_description_signature(member.description)
        if title is None or description is None:
            singletons.append(member)
            continue
        grouped.setdefault((member.company_id, title, description), []).append(member)

    clusters: list[OpportunityCluster] = []
    for (company_id, title, description), candidates in sorted(grouped.items()):
        # Different role metadata is explicit contrary evidence even when the
        # title and normalized core copy happen to match.
        variant_evidence = _variant_evidence(candidates)
        metadata_compatible = (
            _compatible_optional(member.employment_type for member in candidates)
            and _compatible_optional(member.department for member in candidates)
        )
        if len(candidates) < 2 or variant_evidence is None or not metadata_compatible:
            singletons.extend(candidates)
            continue
        ids = tuple(sorted(member.job_instance_id for member in candidates))
        role_identity = f"title:{title}|core_description:{description}"
        evidence = (
            ClusteringEvidence("EXACT_NORMALIZED_TITLE", title, ids),
            ClusteringEvidence("EXACT_CORE_DESCRIPTION_SIGNATURE", description, ids),
            ClusteringEvidence("DECLARED_VARIANT_FIELD_DIFFERENCE", variant_evidence, ids),
        )
        cluster_id = "oc_" + _digest({
            "company_id": company_id,
            "canonical_role_identity": role_identity,
            "clustering_method_version": CLUSTERING_METHOD_VERSION,
        })
        fingerprint = _digest({
            "cluster_id": cluster_id,
            "members": [_member_identity(member) for member in sorted(candidates, key=lambda x: x.job_instance_id)],
            "evidence": [asdict(item) for item in evidence],
        })
        clusters.append(OpportunityCluster(
            cluster_id, company_id, role_identity, ids, fingerprint,
            "EXACT_TITLE_AND_CORE_DESCRIPTION", CLUSTERING_METHOD_VERSION, evidence,
        ))

    for member in sorted(singletons, key=lambda item: (item.company_id, item.job_instance_id)):
        ids = (member.job_instance_id,)
        role_identity = f"source_job_instance:{member.job_instance_id}"
        evidence = (ClusteringEvidence("SINGLETON_SOURCE_IDENTITY", role_identity, ids),)
        cluster_id = "oc_" + _digest({
            "company_id": member.company_id,
            "canonical_role_identity": role_identity,
            "clustering_method_version": CLUSTERING_METHOD_VERSION,
        })
        fingerprint = _digest({
            "cluster_id": cluster_id,
            "members": [_member_identity(member)],
            "evidence": [asdict(evidence[0])],
        })
        clusters.append(OpportunityCluster(
            cluster_id, member.company_id, role_identity, ids, fingerprint,
            "SINGLETON", CLUSTERING_METHOD_VERSION, evidence,
        ))
    return tuple(sorted(clusters, key=lambda item: item.cluster_id))


def _timestamp(value: str | None) -> float:
    if not value:
        return float("-inf")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return float("-inf")


def _market_evidence_is_complete(assessment: CurrentCandidateMarketAssessment) -> bool:
    uncertain = any(
        reason.effect is MarketReasonEffect.SUPPORTS_UNCERTAIN
        for reason in assessment.reasons
    )
    return bool(assessment.evidence) and not uncertain


def _fold(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def _policy_compatible_arrangement(
    member: ClusterMemberEvidence,
    assessment: CurrentCandidateMarketAssessment,
    candidate: CandidateProfile,
) -> bool:
    # Confirmed Czech-compatible remote and accepted onsite/hybrid locations
    # have equal priority; this deliberately creates no universal ordering
    # between the two arrangements.
    if any(
        reason.code is MarketReasonCode.REMOTE_RESIDENCE_CONFIRMED
        for reason in assessment.reasons
    ):
        return True
    normalized_countries = {
        _fold(item.normalized_value)
        for item in assessment.evidence
        if item.kind == "location" and item.normalized_value
    }
    for accepted in candidate.market_access_policy.onsite_hybrid["accepted_locations"]:
        accepted_country = _fold(accepted.get("country"))
        country_matches = accepted_country in normalized_countries or any(
            _fold(location.get("country")) == accepted_country
            for location in member.locations
        )
        accepted_city = _fold(accepted.get("city"))
        city_matches = not accepted_city or any(
            _fold(location.get("city")) == accepted_city
            or re.search(rf"(?<!\w){re.escape(accepted_city)}(?!\w)", _fold(location.get("raw")))
            for location in member.locations
        )
        if country_matches and city_matches:
            return True
    return False


def select_preferred_variant(
    cluster: OpportunityCluster,
    members_by_id: Mapping[int, ClusterMemberEvidence],
    market_by_id: Mapping[int, CurrentCandidateMarketAssessment],
    eligibility_by_id: Mapping[int, EligibilityStatus],
    candidate: CandidateProfile,
) -> PreferredVariantSelection:
    """Select one active, hard-viable member without changing cluster membership."""
    status_priority = {
        CurrentCandidateMarketStatus.IN_SCOPE: 0,
        CurrentCandidateMarketStatus.UNCERTAIN: 1,
        CurrentCandidateMarketStatus.OUT_OF_SCOPE: 2,
    }
    viable = []
    for member_id in cluster.member_job_instance_ids:
        member = members_by_id[member_id]
        if member.lifecycle_state != "ACTIVE":
            continue
        if eligibility_by_id.get(member_id) is EligibilityStatus.INELIGIBLE:
            continue
        if member_id not in market_by_id:
            raise ValueError(f"missing market assessment for job_instance_id={member_id}")
        market = market_by_id[member_id]
        complete_evidence = _market_evidence_is_complete(market)
        compatible_arrangement = _policy_compatible_arrangement(
            member, market, candidate,
        )
        viable.append((
            status_priority[market.status],
            -int(compatible_arrangement),
            -int(complete_evidence),
            -int(member.detail_complete),
            -_timestamp(member.source_evidence_at),
            member.job_instance_id,
        ))
    viable.sort()
    ordered_ids = tuple(item[-1] for item in viable)
    preferred_id = ordered_ids[0] if ordered_ids else None
    reasons: list[VariantRankingReason] = []
    if preferred_id is not None:
        preferred_market = market_by_id[preferred_id].status.value
        reasons.extend((
            VariantRankingReason(
                "MARKET_STATUS_PRIORITY",
                f"{preferred_market} outranks lower market-status categories",
                ordered_ids,
            ),
            VariantRankingReason(
                "CANDIDATE_POLICY_COMPATIBILITY",
                "explicitly compatible location or remote arrangement outranks unresolved alternatives within a market-status category",
                ordered_ids,
            ),
            VariantRankingReason(
                "EVIDENCE_AND_STABLE_TIE_BREAK",
                "market evidence completeness, detail completeness, source currentness, then job_instance_id",
                ordered_ids,
            ),
        ))
    else:
        reasons.append(VariantRankingReason(
            "NO_ACTIVE_HARD_VIABLE_MEMBER",
            "all members are closed or deterministically ineligible",
            cluster.member_job_instance_ids,
        ))
    payload = {
        "cluster_fingerprint": cluster.cluster_fingerprint,
        "candidate_profile_id": candidate.profile_id,
        "market_access_policy_fingerprint": candidate.market_access_policy_fingerprint,
        "preferred_variant_job_instance_id": preferred_id,
        "ordered_member_job_instance_ids": ordered_ids,
        "selection_policy_version": PREFERRED_VARIANT_POLICY_VERSION,
    }
    return PreferredVariantSelection(
        cluster.cluster_id,
        candidate.profile_id,
        candidate.market_access_policy_fingerprint,
        preferred_id,
        ordered_ids,
        tuple(reasons),
        PREFERRED_VARIANT_POLICY_VERSION,
        _digest(payload),
    )
