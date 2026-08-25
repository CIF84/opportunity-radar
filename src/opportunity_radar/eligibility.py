from __future__ import annotations

import re

from opportunity_radar.phase3_models import (
    CandidateProfile, EligibilityEvidence, EligibilityResult, EligibilityStatus, SemanticJobInput,
)


RULE_VERSION = "eligibility-v1"


def evaluate_eligibility(job: SemanticJobInput, candidate: CandidateProfile) -> EligibilityResult:
    text = " ".join(filter(None, [job.title, job.description])).lower()
    facts = candidate.facts
    constraints = candidate.hard_constraints
    evidence: list[EligibilityEvidence] = []

    residence = facts.get("residence", {})
    country = str(residence.get("country", "")).lower()
    city = str(residence.get("city", "")).lower()
    exclusions = {str(value).lower() for value in constraints.get("mandatory_location_exclusions", [])}
    location_text = " ".join(
        " ".join(str(location.get(key) or "") for key in ("raw", "city", "region", "country"))
        for location in job.locations
    ).lower()

    if exclusions and any(value in location_text for value in exclusions):
        evidence.append(EligibilityEvidence(
            "explicit_location_exclusion", "A listed location is explicitly excluded by the candidate.",
            location_text, ", ".join(sorted(exclusions)),
        ))
        return EligibilityResult(EligibilityStatus.INELIGIBLE, tuple(evidence))

    mandatory_relocation = bool(re.search(r"\b(?:must|required to)\s+relocat(?:e|ion)\b", text))
    if mandatory_relocation and constraints.get("relocation", {}).get("prohibited") is True:
        evidence.append(EligibilityEvidence(
            "mandatory_relocation", "The vacancy explicitly requires relocation and the candidate prohibits it.",
            "mandatory relocation", "relocation.prohibited=true",
        ))
        return EligibilityResult(EligibilityStatus.INELIGIBLE, tuple(evidence))

    authorization = facts.get("work_authorization", {})
    auth_match = re.search(r"(?:must|requires?) (?:have|hold) (?:the )?(?:right|authorization) to work in ([a-z ]+)", text)
    if auth_match:
        jurisdiction = auth_match.group(1).strip().replace(" ", "_")
        known = str(authorization.get(jurisdiction, "UNKNOWN")).upper()
        if known in {"NO", "FALSE", "INELIGIBLE"}:
            evidence.append(EligibilityEvidence(
                "work_authorization", "Explicit work-authorization requirement conflicts with a known candidate fact.",
                auth_match.group(0), f"work_authorization.{jurisdiction}={known}",
            ))
            return EligibilityResult(EligibilityStatus.INELIGIBLE, tuple(evidence))
        if known == "UNKNOWN":
            evidence.append(EligibilityEvidence(
                "work_authorization_unknown", "Work authorization is required but candidate authorization is unknown.",
                auth_match.group(0), f"work_authorization.{jurisdiction}=UNKNOWN",
            ))
            return EligibilityResult(EligibilityStatus.UNCERTAIN, tuple(evidence))

    language_levels = {str(x["language"]).lower(): str(x["proficiency"]).upper() for x in facts.get("languages", [])}
    for match in re.finditer(r"(?:fluent|native)\s+(?:proficiency\s+in\s+)?(?:the\s+)?([a-z]+)(?:\s+language)?\s+(?:is\s+)?(?:mandatory|required|necessary)", text):
        language = match.group(1).lower()
        level = language_levels.get(language)
        if level is None:
            evidence.append(EligibilityEvidence(
                "mandatory_language_unknown", f"Mandatory {language.title()} evidence is absent from the profile.",
                match.group(0), None,
            ))
            return EligibilityResult(EligibilityStatus.UNCERTAIN, tuple(evidence))
        if level in {"NONE", "BASIC"}:
            evidence.append(EligibilityEvidence(
                "mandatory_language", f"Mandatory {language.title()} requirement conflicts with candidate proficiency.",
                match.group(0), f"{language}={level}",
            ))
            return EligibilityResult(EligibilityStatus.INELIGIBLE, tuple(evidence))

    if location_text and ((country and country in location_text) or (city and city in location_text)):
        evidence.append(EligibilityEvidence(
            "compatible_location", "A listed location matches the candidate residence.", location_text,
            f"residence={city}, {country}",
        ))
        return EligibilityResult(EligibilityStatus.ELIGIBLE, tuple(evidence))
    if job.work_mode == "remote" and not re.search(r"\b(?:us only|united states only|uk only)\b", text):
        evidence.append(EligibilityEvidence(
            "remote_location_unspecified", "The role is remote but eligible countries are not explicit.",
            "work_mode=remote", f"residence={country or 'unknown'}",
        ))
        return EligibilityResult(EligibilityStatus.UNCERTAIN, tuple(evidence))
    if not location_text:
        evidence.append(EligibilityEvidence(
            "location_unknown", "The vacancy contains insufficient location evidence.", None, None,
        ))
        return EligibilityResult(EligibilityStatus.UNCERTAIN, tuple(evidence))
    evidence.append(EligibilityEvidence(
        "no_explicit_incompatibility", "No explicit deterministic incompatibility was found.",
        location_text, f"residence={city}, {country}",
    ))
    return EligibilityResult(EligibilityStatus.ELIGIBLE, tuple(evidence))

