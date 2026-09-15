from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from opportunity_radar.credential_semantics_validation import (
    CredentialValidationError,
    EmployerCapDecisionRequired,
    append_judgment,
    append_replacement,
    build_safe_final_summary,
    build_safe_termination_summary,
    calculate_metrics,
    cap_diagnostic,
    effective_selected_items,
    load_credential_protocol,
    main,
    prepare_credential_validation,
    render_blind_review,
    select_credential_sample,
    terminate_credential_validation,
)


ROOT = Path(__file__).resolve().parents[1]
BLOCKED_AGGREGATE = ROOT / "output/credential_semantics_validation/spec020-credential-preparation-20260914-v1/aggregate_summary.json"
PREPARED_AGGREGATE = ROOT / "output/credential_semantics_validation/spec020-credential-preparation-20260914-v3/aggregate_summary.json"
TERMINATED_AGGREGATE = ROOT / "output/credential_semantics_validation/spec020-credential-preparation-20260914-v3/aggregate_termination.json"


def _row(index: int, company: str, wording: str = "MUST_HAVE", family: str = "OPERATIONS_PROGRAM") -> dict:
    excerpt = "To qualify, you must have a bachelor's degree. Five years of relevant experience is required."
    return {
        "cluster_id": f"cluster-{index:03d}", "cluster_fingerprint": f"fp-{index}",
        "company_id": company, "company_name": f"Employer {company}",
        "title": f"Program Manager {index}", "locations": [{"raw": "Prague"}],
        "work_mode": "hybrid", "canonical_url": f"https://example.test/{index}",
        "credential_match": "must have a bachelor's degree",
        "qualification_excerpt": excerpt,
        "qualification_excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
        "credential_wording_pattern": wording,
        "credential_sampling_stratum": (
            "QUALIFIED_OR_SUBSTITUTABLE_WORDING"
            if wording in {"EXPLICIT_EQUIVALENT_EXPERIENCE", "MIXED_PREFERRED_CONTEXT"}
            else "DIRECT_MANDATORY_WORDING"
        ),
        "role_family": family,
        "explicit_years_minimum": 5, "elevated_title_context": False,
        "degree_evidence_only_decisive": True, "other_decisive_concepts": [],
        "candidate_evidence": {
            "total_technology_business_years": 20, "completed_bachelors_degree": False,
            "leadership": {"people_management": True, "senior_stakeholder_exposure": True},
            "role_history_summary": ["Senior technology/business leadership."],
            "relevant_asserted_capabilities": [],
        },
    }


def _population(companies: int = 12, per_company: int = 6) -> list[dict]:
    return [_row(index, f"company-{index % companies:02d}") for index in range(companies * per_company)]


def _manifest(protocol=None) -> dict:
    protocol = protocol or load_credential_protocol()
    selection = select_credential_sample(_population(), protocol)
    return {
        "preparation_id": "credential-test", "experiment_id": protocol.experiment_id,
        "protocol_fingerprint": protocol.fingerprint,
        "human_labels": protocol.raw["human_labels"],
        "replacement": protocol.raw["replacement"],
        "sample": selection,
        "population": {
            "wording_pattern_distribution": {"MUST_HAVE": 50},
            "company_distribution": {f"company-{index:02d}": 6 for index in range(12)},
        },
    }


def test_protocol_loads_frozen_two_question_contract():
    protocol = load_credential_protocol(ROOT / "experiments/credential_semantics_validation_v1.yaml")
    assert protocol.version == "credential-semantics-v1"
    assert protocol.raw["sampling"]["target"] == 50
    assert protocol.raw["sampling"]["employer_cap_target"] == 5
    assert protocol.raw["sampling"]["authorized_employer_cap"] == 22
    assert protocol.raw["sampling"]["cap_relaxation_status"] == "HUMAN_AUTHORIZED"
    assert protocol.raw["reporting"]["views"] == [
        "UNWEIGHTED_STRATIFIED_SAMPLE", "EMPLOYER_POPULATION_WEIGHTED_ESTIMATE",
    ]
    assert len(protocol.raw["human_labels"]["credential_semantics"]) == 6
    assert len(protocol.raw["human_labels"]["candidacy_consequence"]) == 4


def test_sample_is_deterministic_and_ignores_hidden_system_fields():
    protocol = load_credential_protocol()
    population = _population()
    changed = copy.deepcopy(population)
    for row in changed:
        row.update({"semantic_cache_status": "HIT", "recommendation": "APPLY", "triage": "SECRET"})
    assert select_credential_sample(population, protocol) == select_credential_sample(changed, protocol)
    source = inspect.getsource(select_credential_sample)
    assert "semantic_cache" not in source
    assert "recommendation" not in source
    assert len(select_credential_sample(population, protocol)["selected"]) == 50


def test_employer_cap_requires_explicit_human_decision_and_proves_minimum():
    protocol = load_credential_protocol()
    population = [
        *[_row(index, "ey") for index in range(116)],
        *[_row(200 + index, "johnson_johnson") for index in range(22)],
        *[_row(300 + index, "schneider_electric") for index in range(6)],
    ]
    diagnostic = cap_diagnostic(population, protocol)
    assert diagnostic["population_count"] == 144
    assert diagnostic["maximum_sample_at_requested_cap"] == 15
    assert diagnostic["minimum_feasible_cap"] == 22
    result = select_credential_sample(population, protocol)
    assert result["employer_cap_effective"] == 22
    assert result["employer_distribution"] == {
        "ey": 22, "johnson_johnson": 22, "schneider_electric": 6,
    }


def test_approved_cap_relaxation_can_freeze_without_global_resampling():
    protocol = load_credential_protocol()
    population = [
        *[_row(index, "ey") for index in range(116)],
        *[_row(200 + index, "johnson_johnson") for index in range(22)],
        *[_row(300 + index, "schneider_electric") for index in range(6)],
    ]
    result = select_credential_sample(population, protocol)
    assert result["employer_cap_effective"] == 22
    assert len(result["reserves"]["DIRECT_MANDATORY_WORDING"]) == 5


def test_blind_packet_preserves_exact_modal_wording_and_hides_system_evidence():
    manifest = _manifest()
    text = render_blind_review(manifest, manifest["sample"]["selected"][:1])
    assert "must have a bachelor's degree" in text
    assert "Question A" in text and "Question B" in text
    for hidden in ("EXCESSIVE_STRETCH", "semantic_cache", "recommendation", "triage"):
        assert hidden.lower() not in text.lower()


def test_judgments_are_controlled_append_only_and_supersession_safe(tmp_path):
    manifest = _manifest()
    judgments = tmp_path / "judgments.jsonl"
    replacements = tmp_path / "replacements.jsonl"
    first = append_judgment(
        manifest, judgments, replacements, "HARD_CREDENTIAL", "DEGREE_GAP_DECISIVE",
        review_number=1, reasons=["EXPLICIT_MANDATORY_WORDING"], note="private note",
    )
    with pytest.raises(CredentialValidationError, match="current judgment exists"):
        append_judgment(
            manifest, judgments, replacements, "PREFERRED_CREDENTIAL", "DEGREE_GAP_NOT_DECISIVE",
            review_number=1,
        )
    second = append_judgment(
        manifest, judgments, replacements, "PREFERRED_CREDENTIAL", "DEGREE_GAP_NOT_DECISIVE",
        review_number=1, supersedes=first["record_id"],
    )
    assert second["supersedes_record_id"] == first["record_id"]
    with pytest.raises(CredentialValidationError, match="invalid controlled reason"):
        append_judgment(
            manifest, judgments, replacements, "HARD_CREDENTIAL", "DEGREE_GAP_DECISIVE",
            review_number=2, reasons=["INVENTED"],
        )


def test_replacement_uses_frozen_same_wording_stratum_and_cannot_follow_judgment(tmp_path):
    manifest = _manifest()
    judgments = tmp_path / "judgments.jsonl"
    replacements = tmp_path / "replacements.jsonl"
    value = append_replacement(
        manifest, replacements, judgments, 1, "INVALID_SOURCE_EVIDENCE",
    )
    effective = effective_selected_items(manifest, json.loads(json.dumps([value])))
    first = effective[0]
    assert first["cluster_id"] == value["replacement_cluster_id"]
    assert first["credential_sampling_stratum"] == value["major_stratum"]
    append_judgment(
        manifest, judgments, replacements, "HARD_CREDENTIAL", "DEGREE_GAP_DECISIVE",
        review_number=1,
    )
    with pytest.raises(CredentialValidationError, match="after judgment"):
        append_replacement(manifest, replacements, judgments, 1, "STALE_SOURCE_EVIDENCE")


def test_report_stays_blind_until_complete_then_counterfactuals_are_deterministic(tmp_path):
    manifest = _manifest()
    records = []
    selected = manifest["sample"]["selected"]
    for item in selected[:-1]:
        records.append({
            "record_id": f"j-{item['review_number']}", "preparation_id": manifest["preparation_id"],
            "cluster_id": item["cluster_id"], "credential_label": "HARD_CREDENTIAL",
            "consequence_label": "DEGREE_GAP_DECISIVE", "supersedes_record_id": None,
        })
    progress = calculate_metrics(manifest, records, [])
    assert progress == {"status": "IN_PROGRESS", "reviewed": 49, "target": 50, "remaining": 1}
    assert "current_rule_precision" not in progress
    last = selected[-1]
    records.append({
        "record_id": "j-last", "preparation_id": manifest["preparation_id"],
        "cluster_id": last["cluster_id"], "credential_label": "DEGREE_OR_EQUIVALENT_EXPERIENCE",
        "consequence_label": "EXPERIENCE_PLAUSIBLY_SUBSTITUTES", "supersedes_record_id": None,
    })
    complete = calculate_metrics(manifest, records, [])
    assert complete["status"] == "COMPLETE"
    assert complete["current_rule_precision"]["strict_count"] == 49
    assert complete == calculate_metrics(manifest, copy.deepcopy(records), [])


def test_repository_safe_result_excludes_vacancy_and_human_note(tmp_path):
    manifest = _manifest()
    judgments = tmp_path / "judgments.jsonl"
    judgments.write_text("{}\n", encoding="utf-8")
    metrics = {
        "status": "COMPLETE", "credential_semantics_distribution": {"HARD_CREDENTIAL": 50},
        "candidacy_consequence_distribution": {"DEGREE_GAP_DECISIVE": 50},
    }
    safe = build_safe_final_summary(manifest, metrics, judgments)
    text = json.dumps(safe)
    assert "private note" not in text
    assert "Program Manager" not in text
    assert "example.test" not in text
    assert "cluster-" not in text


def test_authorized_preparation_is_read_only_zero_call_and_freezes_sample(tmp_path, monkeypatch):
    database = tmp_path / "state.sqlite3"
    database.write_bytes(b"read-only operational fixture")
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    mtime = database.stat().st_mtime_ns
    population = [
        *[_row(index, "ey") for index in range(116)],
        *[_row(200 + index, "johnson_johnson") for index in range(22)],
        *[_row(300 + index, "schneider_electric") for index in range(6)],
    ]
    metadata = {
        "source_population_count": 144, "role_family_distribution": {"OPERATIONS_PROGRAM": 144},
        "wording_pattern_distribution": {"MUST_HAVE": 144}, "years_context_count": 144,
        "company_distribution": {"ey": 116, "johnson_johnson": 22, "schneider_electric": 6},
        "degree_only_decisive_count": 144, "population_fingerprint": "p" * 64,
        "stretch_rules_fingerprint": "s" * 64, "candidate_full_profile_fingerprint": "f" * 64,
        "candidate_semantic_profile_fingerprint": "m" * 64,
    }
    monkeypatch.setattr(
        "opportunity_radar.credential_semantics_validation.build_credential_population",
        lambda *args, **kwargs: (population, metadata),
    )
    monkeypatch.setattr(
        "requests.post", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("external call")),
    )
    result = prepare_credential_validation(database, output_root=tmp_path / "output")
    assert result["status"] == "PREPARED_AWAITING_HUMAN_REVIEW"
    assert result["aggregate"]["sample"]["selected_count"] == 50
    assert result["aggregate"]["integrity"]["external_semantic_calls"] == 0
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert database.stat().st_mtime_ns == mtime
    directory = tmp_path / "output" / result["manifest"]["preparation_id"]
    assert (directory / "manifest.json").exists()
    assert (directory / "blind_review.md").exists()


def test_private_credential_evidence_is_ignored_but_aggregate_is_trackable():
    private = (
        "output/credential_semantics_validation/example/manifest.json",
        "output/credential_semantics_validation/example/blind_review.md",
        "output/credential_semantics_validation/example/detailed_report.json",
        "data/credential_semantics_validation/judgments.jsonl",
    )
    for path in private:
        assert subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0
    assert subprocess.run(
        ["git", "check-ignore", "-q", "output/credential_semantics_validation/example/aggregate_summary.json"], cwd=ROOT,
    ).returncode == 1


def test_repository_safe_preparation_receipt_records_the_fail_closed_stop():
    result = json.loads(BLOCKED_AGGREGATE.read_text(encoding="utf-8"))
    assert result["verified_population"]["count"] == 144
    assert result["sampling_stop"]["maximum_sample_at_requested_cap"] == 15
    assert result["sampling_stop"]["minimum_feasible_cap"] == 22
    assert result["integrity"] == {
        "sample_frozen": False,
        "human_review_started": False,
        "human_judgments_created": 0,
        "external_semantic_calls": 0,
        "live_source_calls": 0,
        "sqlite_writes": 0,
    }


def test_repository_safe_prepared_receipt_records_frozen_design_and_integrity():
    result = json.loads(PREPARED_AGGREGATE.read_text(encoding="utf-8"))
    assert result["status"] == "PREPARED_AWAITING_HUMAN_REVIEW"
    assert result["verified_population_count"] == 144
    assert result["sample"]["selected_count"] == 50
    assert result["sample"]["employer_cap_effective"] == 22
    assert result["sample"]["employer_distribution"] == {
        "ey": 22, "johnson_johnson": 22, "schneider_electric": 6,
    }
    assert result["sample"]["reserve_counts"] == {
        "DIRECT_MANDATORY_WORDING": 5,
        "QUALIFIED_OR_SUBSTITUTABLE_WORDING": 5,
    }
    assert result["reporting_policy"]["balanced_sample_proportions_are_population_prevalence"] is False
    assert result["reporting_policy"]["complete_employer_coverage"] == {"schneider_electric": 6}
    assert result["integrity"]["deterministic_selection_replay"] is True
    assert result["integrity"]["exact_qualification_wording_preserved"] is True
    assert result["integrity"]["database_unchanged"] is True
    assert result["integrity"]["human_judgments_created"] == 0
    assert result["integrity"]["external_semantic_calls"] == 0


def _termination_records(manifest: dict) -> list[dict]:
    rows = []
    for item in manifest["sample"]["selected"][:20]:
        number = item["review_number"]
        a, b = (
            ("INVALID_OR_STALE_EVIDENCE", "NEED_MORE_INFORMATION") if number <= 12
            else ("HARD_CREDENTIAL", "EXPERIENCE_PLAUSIBLY_SUBSTITUTES") if number <= 18
            else ("HARD_CREDENTIAL", "DEGREE_GAP_DECISIVE")
        )
        rows.append({
            "record_id": f"judgment-{number}", "preparation_id": manifest["preparation_id"],
            "review_number": number, "cluster_id": item["cluster_id"],
            "credential_label": a, "consequence_label": b,
            "note": "private human note", "reasons": [], "supersedes_record_id": None,
        })
    return rows


def test_termination_receipt_is_sanitized_incomplete_and_has_no_final_gates():
    manifest = _manifest()
    preparation = json.loads(PREPARED_AGGREGATE.read_text(encoding="utf-8"))
    preparation["preparation_id"] = manifest["preparation_id"]
    summary = build_safe_termination_summary(
        manifest, preparation, _termination_records(manifest), [],
        judgment_log_sha256="j" * 64, replacement_log_sha256=None,
    )
    assert summary["status"] == "TERMINATED_SOURCE_DECAY_CONFOUNDED"
    assert summary["coverage"]["reviewed_count"] == 20
    assert summary["coverage"]["invalid_or_stale_count"] == 12
    assert summary["coverage"]["interpretable_question_a_label_counts"] == {"HARD_CREDENTIAL": 8}
    assert summary["coverage"]["interpretable_question_b_label_counts"] == {
        "DEGREE_GAP_DECISIVE": 2, "EXPERIENCE_PLAUSIBLY_SUBSTITUTES": 6,
    }
    assert summary["integrity"]["predeclared_final_50_case_gates_calculated"] is False
    assert "current_rule_precision" not in json.dumps(summary)
    assert "private human note" not in json.dumps(summary)
    assert "Program Manager" not in json.dumps(summary)
    assert "example.test" not in json.dumps(summary)
    assert "cluster-" not in json.dumps(summary)


def test_termination_requires_exact_frozen_review_state_and_is_immutable(tmp_path):
    manifest = _manifest()
    preparation = json.loads(PREPARED_AGGREGATE.read_text(encoding="utf-8"))
    preparation["preparation_id"] = manifest["preparation_id"]
    directory = tmp_path / manifest["preparation_id"]
    directory.mkdir()
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "aggregate_summary.json").write_text(json.dumps(preparation), encoding="utf-8")
    judgments = tmp_path / "judgments.jsonl"
    judgments.write_text("".join(json.dumps(row) + "\n" for row in _termination_records(manifest)), encoding="utf-8")
    before = judgments.read_bytes()
    replacements = tmp_path / "replacements.jsonl"
    summary = terminate_credential_validation(tmp_path, manifest["preparation_id"], judgments, replacements)
    assert summary["status"] == "TERMINATED_SOURCE_DECAY_CONFOUNDED"
    assert judgments.read_bytes() == before
    assert not replacements.exists()
    with pytest.raises(CredentialValidationError, match="terminal receipt already exists"):
        terminate_credential_validation(tmp_path, manifest["preparation_id"], judgments, replacements)
    (directory / "aggregate_termination.json").unlink()
    judgments.write_text("".join(json.dumps(row) + "\n" for row in _termination_records(manifest)[:-1]), encoding="utf-8")
    with pytest.raises(CredentialValidationError, match="exactly the first 20"):
        terminate_credential_validation(tmp_path, manifest["preparation_id"], judgments, replacements)


def test_repository_safe_terminal_receipt_is_incomplete_and_private_free():
    result = json.loads(TERMINATED_AGGREGATE.read_text(encoding="utf-8"))
    assert result["status"] == "TERMINATED_SOURCE_DECAY_CONFOUNDED"
    assert result["coverage"]["reviewed_count"] == 20
    assert result["coverage"]["unreviewed_count"] == 30
    assert result["coverage"]["invalid_or_stale_count"] == 12
    assert result["coverage"]["substantively_interpretable_count"] == 8
    assert result["coverage"]["interpretable_question_b_label_counts"] == {
        "DEGREE_GAP_DECISIVE": 2, "EXPERIENCE_PLAUSIBLY_SUBSTITUTES": 6,
    }
    assert result["integrity"]["predeclared_final_50_case_gates_calculated"] is False
    assert result["integrity"]["final_counterfactual_performance_calculated"] is False
    text = json.dumps(result)
    for private in ("Page no longer exists.", "JavaScript remains", "SAP knowledge", "cluster_id", "canonical_url"):
        assert private not in text
    assert subprocess.run(
        ["git", "check-ignore", "-q", str(TERMINATED_AGGREGATE.relative_to(ROOT))], cwd=ROOT,
    ).returncode == 1


def test_terminal_cli_refuses_new_judgments_and_reports_only_terminal_receipt(tmp_path, monkeypatch, capsys):
    manifest = _manifest()
    directory = tmp_path / manifest["preparation_id"]
    directory.mkdir()
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "aggregate_termination.json").write_text(
        json.dumps({"status": "TERMINATED_SOURCE_DECAY_CONFOUNDED"}), encoding="utf-8",
    )
    judgments = tmp_path / "judgments.jsonl"
    protocol = SimpleNamespace(raw={"outputs": {
        "root": str(tmp_path), "judgments": str(judgments),
        "replacements": str(tmp_path / "replacements.jsonl"),
    }})
    monkeypatch.setattr(
        "opportunity_radar.credential_semantics_validation.load_credential_protocol",
        lambda *args: protocol,
    )
    monkeypatch.setattr(sys, "argv", [
        "credential-cli", "record", manifest["preparation_id"], "--review-number", "21",
        "HARD_CREDENTIAL", "DEGREE_GAP_DECISIVE",
    ])
    with pytest.raises(CredentialValidationError, match="preparation is terminated"):
        main()
    assert not judgments.exists()
    monkeypatch.setattr(sys, "argv", ["credential-cli", "report", manifest["preparation_id"]])
    assert main() == 0
    assert "TERMINATED_SOURCE_DECAY_CONFOUNDED" in capsys.readouterr().out
