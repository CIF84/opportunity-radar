from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
from pathlib import Path

import pytest

from opportunity_radar.credential_evidence_validation import (
    SEMANTIC_CLASSES,
    CredentialEvidenceError,
    CredentialEvidenceSnapshot,
    EvidenceValidity,
    SourceCurrentness,
    append_invalid_replacement,
    append_judgment,
    build_candidate_substitution_projection,
    calculate_progress,
    effective_selected_items,
    evidence_remains_valid_when_currentness_changes,
    evidence_validity,
    load_credential_evidence_protocol,
    prepare_credential_evidence_validation,
    render_blind_review,
    select_semantically_diverse_sample,
)
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy


ROOT = Path(__file__).resolve().parents[1]
AGGREGATE = ROOT / (
    "output/credential_evidence_validation/"
    "spec021-credential-evidence-preparation-20260916-v2/aggregate_summary.json"
)


def _candidate_projection(index: int = 0) -> dict:
    payload = {
        "completed_bachelors_degree": False,
        "career_years": {"total_years": 20, "technology_years": 20},
        "leadership": {"people_management": True},
        "experience_domains": [{"domain_id": "business_operations", "depth": "DEEP"}],
        "role_history_summary": ["Senior business and technology leadership."],
        "direct_capability_evidence": [] if index % 4 else [{
            "capability_id": "business_analytics", "level": "EXPERT", "confidence": "HIGH",
            "matched_job_term": "analytics", "candidate_source": "capabilities[business_analytics]",
        }],
        "adjacent_transferable_evidence": [],
        "explicit_none_or_developing_evidence": [],
        "omitted_capability_semantics": "UNKNOWN_NOT_NONE",
    }
    payload["projection_fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    return payload


def _snapshot(index: int, evidence_class: str, company: str | None = None) -> dict:
    company = company or f"company-{index % 12:02d}"
    projection = _candidate_projection(index)
    values = {
        "job_instance_id": index + 1,
        "job_observation_id": index + 100,
        "company_id": company,
        "external_job_id": f"external-{index}",
        "employer_name": f"Employer {company}",
        "role_title": f"Role {index}",
        "source": "fixture",
        "source_url": f"https://example.test/{index}",
        "observed_at": "2026-09-16T00:00:00+00:00",
        "retrieved_at": "2026-09-16T00:00:00+00:00",
        "exact_credential_statements": ("A bachelor's degree is required.",),
        "bounded_qualification_context": "Qualifications. A bachelor's degree is required. Five years of experience.",
        "exact_modal_terms": ("required",),
        "explicit_year_requirements": ("Five years of experience",),
        "related_domain_technical_requirements": ("Five years of experience.",),
        "normalized_credential_concept": (
            "PROFESSIONAL_LICENSE" if evidence_class == "CONSTITUTIVE_OR_REGULATED"
            else "BACHELORS_DEGREE"
        ),
        "source_content_fingerprint": f"source-{index:04d}",
        "evidence_completeness": {
            "stable_identity": True, "observation_identity": True,
            "observation_timestamp": True, "source_content_fingerprint": True,
            "exact_credential_wording": True, "bounded_context": True,
        },
        "evidence_validity": "VALID_FROZEN_EVIDENCE",
        "source_currentness": "SOURCE_CURRENTNESS_NOT_CHECKED",
        "semantic_evidence_class": evidence_class,
        "candidate_substitution_signal": (
            "DIRECT_MATCH_PRESENT" if projection["direct_capability_evidence"]
            else "NO_ASSERTED_MATCH"
        ),
        "candidate_substitution_evidence": projection,
    }
    return CredentialEvidenceSnapshot.create(**values).payload()


def _population() -> list[dict]:
    rows = []
    for class_index, evidence_class in enumerate(SEMANTIC_CLASSES):
        for offset in range(12):
            rows.append(_snapshot(class_index * 100 + offset, evidence_class))
    return rows


def _manifest(protocol=None) -> dict:
    protocol = protocol or load_credential_evidence_protocol()
    population = _population()
    return {
        "preparation_id": "spec021-test",
        "experiment_id": protocol.experiment_id,
        "protocol_version": protocol.raw["protocol_version"],
        "human_labels": protocol.raw["human_labels"],
        "replacement": protocol.raw["replacement"],
        "evidence_population": {"metadata": {}, "snapshots": population},
        "sample": select_semantically_diverse_sample(population, protocol),
    }


def test_protocol_is_distinct_and_targets_every_semantic_class():
    protocol = load_credential_evidence_protocol()
    assert protocol.experiment_id == "EXP-CREDENTIAL-EVIDENCE-SEMANTICS-002"
    assert protocol.raw["protocol_version"] == "credential-evidence-semantics-v2"
    assert protocol.raw["sampling"]["target"] == 36
    assert set(protocol.raw["sampling"]["class_targets"]) == set(SEMANTIC_CLASSES)


def test_dead_url_currentness_does_not_invalidate_frozen_evidence():
    snapshot = CredentialEvidenceSnapshot(**_snapshot(1, "EXPLICIT_HARD"))
    assert evidence_remains_valid_when_currentness_changes(
        snapshot, SourceCurrentness.SOURCE_CURRENTLY_UNAVAILABLE
    )
    assert snapshot.evidence_validity == "VALID_FROZEN_EVIDENCE"


def test_incomplete_capture_is_invalid_but_currentness_is_not_a_completeness_field():
    completeness = {
        "stable_identity": True, "observation_identity": True,
        "observation_timestamp": True, "source_content_fingerprint": True,
        "exact_credential_wording": False, "bounded_context": True,
    }
    assert evidence_validity(completeness) is EvidenceValidity.INSUFFICIENT_CAPTURE
    assert "source_currentness" not in completeness


def test_exact_modal_wording_context_and_snapshot_are_immutable_and_fingerprinted():
    first = CredentialEvidenceSnapshot(**_snapshot(2, "EXPLICIT_HARD"))
    changed = dict(_snapshot(2, "EXPLICIT_HARD"))
    changed["exact_modal_terms"] = ("preferred",)
    changed.pop("snapshot_fingerprint")
    second = CredentialEvidenceSnapshot.create(**changed)
    assert first.exact_credential_statements == ("A bachelor's degree is required.",)
    assert first.snapshot_fingerprint != second.snapshot_fingerprint
    with pytest.raises(Exception):
        first.exact_modal_terms = ("preferred",)  # type: ignore[misc]


def test_candidate_projection_is_deterministic_and_excludes_preferences():
    taxonomy = load_taxonomy(ROOT / "config/taxonomy.yaml")
    profile = load_candidate_profile(ROOT / "config/candidate.yaml", taxonomy)
    protocol = load_credential_evidence_protocol()
    first = build_candidate_substitution_projection(
        profile, taxonomy, "Business analytics and strategic leadership.", protocol
    )
    second = build_candidate_substitution_projection(
        profile, taxonomy, "Business analytics and strategic leadership.", protocol
    )
    assert first == second
    assert "preferences" not in first and "decision_preferences" not in first
    assert first["omitted_capability_semantics"] == "UNKNOWN_NOT_NONE"
    source = inspect.getsource(build_candidate_substitution_projection)
    assert "profile.preferences" not in source
    assert "profile.decision_preferences" not in source


def test_semantic_selection_is_deterministic_oversamples_rare_classes_and_ignores_hidden_fields():
    protocol = load_credential_evidence_protocol()
    population = _population()
    changed = copy.deepcopy(population)
    for item in changed:
        item.update({
            "recommendation": "APPLY", "semantic_score": 10,
            "cache_status": "HIT", "stretch_class": "EXCESSIVE_STRETCH",
            "historical_human_label": "SECRET", "candidate_preferences": ["secret"],
        })
    first = select_semantically_diverse_sample(population, protocol)
    second = select_semantically_diverse_sample(changed, protocol)
    assert first == second
    assert len(first["selected"]) == 36
    assert first["semantic_class_distribution"] == protocol.raw["sampling"]["class_targets"]
    assert all(len(values) == 2 for values in first["reserves"].values())


def test_blind_review_contains_frozen_evidence_but_no_hidden_sampling_class():
    text = render_blind_review(_manifest())
    assert "A bachelor's degree is required." in text
    assert "Question A" in text and "Question B" in text
    for hidden in (
        "semantic_evidence_class", "candidate_substitution_signal",
        "EXCESSIVE_STRETCH", "semantic_cache_status", "triage_score",
    ):
        assert hidden not in text


def test_controlled_gap_judgments_are_append_only_and_supersession_safe(tmp_path):
    manifest = _manifest()
    judgments = tmp_path / "judgments.jsonl"
    replacements = tmp_path / "replacements.jsonl"
    first = append_judgment(
        manifest, judgments, replacements,
        "HARD_CREDENTIAL", "EXPERIENCE_PARTIALLY_SUBSTITUTES",
        review_number=1, independent_gaps=["TECHNICAL_SKILL_GAP"], note="private",
    )
    with pytest.raises(CredentialEvidenceError, match="current judgment exists"):
        append_judgment(
            manifest, judgments, replacements,
            "HARD_CREDENTIAL", "NEED_MORE_INFORMATION", review_number=1,
        )
    second = append_judgment(
        manifest, judgments, replacements,
        "HARD_CREDENTIAL", "EXPERIENCE_STRONGLY_SUBSTITUTES",
        review_number=1, supersedes=first["record_id"],
    )
    assert second["supersedes_record_id"] == first["record_id"]
    with pytest.raises(CredentialEvidenceError, match="invalid independent"):
        append_judgment(
            manifest, judgments, replacements,
            "HARD_CREDENTIAL", "NEED_MORE_INFORMATION", review_number=2,
            independent_gaps=["INVENTED_GAP"],
        )


def test_replacement_requires_capture_invalidity_and_preserves_semantic_class(tmp_path):
    manifest = _manifest()
    judgments = tmp_path / "judgments.jsonl"
    replacements = tmp_path / "replacements.jsonl"
    with pytest.raises(CredentialEvidenceError, match="controlled evidence-invalidity"):
        append_invalid_replacement(
            manifest, replacements, judgments,
            review_number=1, invalidity_reason="SOURCE_CURRENTLY_UNAVAILABLE",
        )
    value = append_invalid_replacement(
        manifest, replacements, judgments,
        review_number=1, invalidity_reason="INSUFFICIENT_CAPTURE",
    )
    effective = effective_selected_items(manifest, [value])
    assert effective[0]["snapshot_fingerprint"] == value["replacement_snapshot_fingerprint"]
    assert effective[0]["semantic_evidence_class"] == value["semantic_evidence_class"]


def test_saturation_checkpoint_is_blind_safe_and_never_auto_stops():
    manifest = _manifest()
    judgments = []
    for item in manifest["sample"]["selected"][:10]:
        judgments.append({
            "record_id": f"j-{item['review_number']}",
            "preparation_id": manifest["preparation_id"],
            "review_number": item["review_number"],
            "snapshot_fingerprint": item["snapshot_fingerprint"],
            "credential_semantics_label": "HARD_CREDENTIAL",
            "experiential_substitution_label": "EXPERIENCE_PARTIALLY_SUBSTITUTES",
            "independent_capability_gaps": [],
            "recorded_at": f"2026-09-16T00:00:{item['review_number']:02d}+00:00",
            "supersedes_record_id": None,
        })
    result = calculate_progress(manifest, judgments, [])
    checkpoint = result["saturation_checkpoint"]
    assert checkpoint["automatic_stop"] is False
    assert "future" not in json.dumps(checkpoint).lower()
    assert "semantic_class_distribution" not in checkpoint


def test_preparation_is_zero_call_read_only_and_safe_summary_excludes_private_rows(tmp_path, monkeypatch):
    database = tmp_path / "operational.sqlite3"
    database.write_bytes(b"read-only-operational-fixture")
    before = database.read_bytes()
    mtime = database.stat().st_mtime_ns
    population = _population()
    metadata = {
        "detailed_observation_rows_searched": 84,
        "distinct_job_instances_searched": 84,
        "unique_job_content_versions_searched": 84,
        "latest_observation_rows_searched": 84,
        "historical_unique_content_versions_searched": 0,
        "reconstructable_valid_evidence_count": 84,
        "invalid_or_incomplete_capture_count": 0,
        "semantic_class_distribution": {item: 12 for item in SEMANTIC_CLASSES},
        "company_distribution": {f"company-{i:02d}": 7 for i in range(12)},
        "credential_concept_distribution": {"BACHELORS_DEGREE": 84},
        "candidate_substitution_signal_distribution": {
            "DIRECT_MATCH_PRESENT": 21, "NO_ASSERTED_MATCH": 63,
        },
        "currentness_distribution": {"SOURCE_CURRENTNESS_NOT_CHECKED": 84},
        "evidence_population_fingerprint": "e" * 64,
        "candidate_full_profile_fingerprint": "f" * 64,
        "candidate_semantic_profile_fingerprint": "s" * 64,
        "candidate_projection_fingerprint": "p" * 64,
    }
    monkeypatch.setattr(
        "opportunity_radar.credential_evidence_validation.build_evidence_population",
        lambda *args, **kwargs: (population, metadata),
    )
    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("external call")),
    )
    result = prepare_credential_evidence_validation(
        database, output_root=tmp_path / "output"
    )
    assert result["status"] == "PREPARED_AWAITING_HUMAN_REVIEW_APPROVAL"
    assert database.read_bytes() == before and database.stat().st_mtime_ns == mtime
    safe = json.dumps(result["aggregate"])
    for private in ("Role 1", "example.test", "job_instance_id", "exact_credential_statements"):
        assert private not in safe
    assert result["aggregate"]["integrity"]["external_semantic_calls"] == 0
    assert result["aggregate"]["integrity"]["sqlite_writes"] == 0


def test_private_v2_evidence_is_ignored_but_sanitized_aggregate_is_trackable():
    private = (
        "output/credential_evidence_validation/example/manifest.json",
        "output/credential_evidence_validation/example/blind_review.md",
        "output/credential_evidence_validation/example/detailed_report.json",
        "data/credential_evidence_validation/judgments.jsonl",
        "data/credential_evidence_validation/replacements.jsonl",
    )
    for path in private:
        assert subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0
    assert subprocess.run(
        ["git", "check-ignore", "-q", "output/credential_evidence_validation/example/aggregate_summary.json"],
        cwd=ROOT,
    ).returncode == 1


def test_repository_safe_v2_receipt_records_frozen_diversity_and_zero_calls():
    result = json.loads(AGGREGATE.read_text(encoding="utf-8"))
    assert result["status"] == "PREPARED_AWAITING_HUMAN_REVIEW_APPROVAL"
    assert result["proposed_frozen_sample"]["selected_count"] == 36
    assert set(result["proposed_frozen_sample"]["semantic_class_distribution"]) == set(SEMANTIC_CLASSES)
    assert result["integrity"]["operational_database_unchanged"] is True
    assert result["integrity"]["human_review_started"] is False
    assert result["integrity"]["human_judgments_created"] == 0
    assert result["integrity"]["external_semantic_calls"] == 0
    assert result["integrity"]["live_source_calls"] == 0
    text = json.dumps(result)
    for private in ("job_instance_id", "role_title", "source_url", "exact_credential_statements"):
        assert private not in text
