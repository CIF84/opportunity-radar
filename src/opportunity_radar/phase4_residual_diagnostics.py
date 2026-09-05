from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import uuid
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.live_validation import _active_rows, _semantic_job, _usable
from opportunity_radar.market_status import (
    evaluate_current_candidate_market,
    load_market_normalization_rules,
)
from opportunity_radar.phase3_config import digest, load_candidate_profile, load_taxonomy
from opportunity_radar.phase4_replay import (
    DEFAULT_OUTPUT_ROOT,
    ReplayError,
    build_sanitized_summary,
    load_replay_config,
    run_replay,
)


DEFAULT_CONFIG = Path("experiments/phase4_residual_diagnostics_v1.yaml")
EXPERIMENT_TYPE = "POST_HOC_CORRECTED_RETROSPECTIVE"
RESIDUAL_CLASSIFICATIONS = {
    "FIXED_DETERMINISTIC_NORMALIZATION",
    "FIXED_GENERIC_PREFERENCE_MATCHING",
    "CORRECTLY_UNCERTAIN_MARKET_ACCESS",
    "UNREPRESENTED_PREFERENCE_OR_CONVICTION",
    "SEMANTIC_V1_RESIDUAL",
    "OTHER",
}
DIAGNOSTIC_KINDS = {
    "NORMALIZATION_CONTROL",
    "PREFERENCE_RESIDUAL",
    "CONSERVATIVE_MARKET_UNCERTAINTY",
    "SEMANTIC_CONTROL",
}


@dataclass(frozen=True)
class DiagnosticCase:
    review_number: int
    diagnostic_kind: str
    expected_existing_preference_concepts: tuple[str, ...]
    unrepresented_human_factor: str | None
    root_layer: str


@dataclass(frozen=True)
class ResidualDiagnosticsConfig:
    experiment_id: str
    base_replay_config: str
    parent_aggregate_path: str
    parent_detailed_replay_path: str
    cases: tuple[DiagnosticCase, ...]
    fingerprint: str


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_residual_diagnostics_config(
    path: str | Path = DEFAULT_CONFIG,
    taxonomy_path: str | Path = "config/taxonomy.yaml",
) -> ResidualDiagnosticsConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version", "experiment_id", "experiment_type",
        "base_replay_config", "parent_aggregate_path",
        "parent_detailed_replay_path", "diagnostic_cases",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ReplayError("residual diagnostics configuration has an invalid schema")
    if raw["schema_version"] != 1:
        raise ReplayError("unsupported residual diagnostics schema version")
    if raw["experiment_type"] != EXPERIMENT_TYPE:
        raise ReplayError(f"experiment_type must be {EXPERIMENT_TYPE}")
    taxonomy = load_taxonomy(taxonomy_path)
    cases: list[DiagnosticCase] = []
    for item in raw["diagnostic_cases"]:
        if not isinstance(item, dict) or set(item) != {
            "review_number", "diagnostic_kind",
            "expected_existing_preference_concepts",
            "unrepresented_human_factor", "root_layer",
        }:
            raise ReplayError("residual diagnostic case has an invalid schema")
        if item["diagnostic_kind"] not in DIAGNOSTIC_KINDS:
            raise ReplayError("unknown residual diagnostic kind")
        concepts = item["expected_existing_preference_concepts"]
        if not isinstance(concepts, list) or any(not isinstance(value, str) for value in concepts):
            raise ReplayError("expected preference concepts must be a string list")
        for concept_id in concepts:
            taxonomy.require(concept_id, "residual diagnostic preference concept")
        cases.append(DiagnosticCase(
            int(item["review_number"]), str(item["diagnostic_kind"]),
            tuple(concepts), item["unrepresented_human_factor"],
            str(item["root_layer"]),
        ))
    reviews = [item.review_number for item in cases]
    if len(reviews) != len(set(reviews)):
        raise ReplayError("residual diagnostic review numbers must be unique")
    if set(reviews) != {10, 13, 17, 18, 23, 27}:
        raise ReplayError("SPEC-007 diagnostics must cover reviews 10, 13, 17, 18, 23, and 27")
    return ResidualDiagnosticsConfig(
        str(raw["experiment_id"]), str(raw["base_replay_config"]),
        str(raw["parent_aggregate_path"]), str(raw["parent_detailed_replay_path"]),
        tuple(cases), digest(raw),
    )


def classify_diagnostic_case(
    case: DiagnosticCase,
    before: dict[str, Any],
    after: dict[str, Any],
) -> str:
    """Classify a diagnostic from explicit before/after evidence."""
    if before["market_assessment"]["status"] != after["market_assessment"]["status"]:
        return "FIXED_DETERMINISTIC_NORMALIZATION"
    before_effects = before["preference_assessment"]["matched_effects"]
    after_effects = after["preference_assessment"]["matched_effects"]
    if before_effects != after_effects:
        return "FIXED_GENERIC_PREFERENCE_MATCHING"
    if case.diagnostic_kind == "CONSERVATIVE_MARKET_UNCERTAINTY" and after["market_assessment"]["status"] == "UNCERTAIN":
        return "CORRECTLY_UNCERTAIN_MARKET_ACCESS"
    if case.diagnostic_kind == "PREFERENCE_RESIDUAL":
        return "UNREPRESENTED_PREFERENCE_OR_CONVICTION"
    if case.diagnostic_kind == "SEMANTIC_CONTROL":
        return "SEMANTIC_V1_RESIDUAL"
    return "OTHER"


def _semantic_payloads(base_config: str, postings: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    replay_config = load_replay_config(base_config)
    connection = sqlite3.connect(
        f"file:{Path(replay_config.baseline['database_path']).resolve()}?mode=ro&immutable=1",
        uri=True,
    )
    try:
        connection.execute("PRAGMA query_only = ON")
        result = {}
        for posting in postings:
            row = connection.execute(
                "SELECT assessment_json FROM semantic_assessments WHERE semantic_assessment_id=?",
                (posting["semantic_assessment_id"],),
            ).fetchone()
            if row is None:
                raise ReplayError(
                    f"missing cached semantic assessment for review {posting['review_number']}"
                )
            result[posting["review_number"]] = json.loads(row[0])
        return result
    finally:
        connection.close()


def _cluster_for_review(artifact: dict[str, Any], review_number: int) -> dict[str, Any]:
    return next(
        item for item in artifact["opportunity_level"]
        if review_number in item["review_numbers"]
    )


def _diagnostic_rows(
    config: ResidualDiagnosticsConfig,
    parent: dict[str, Any],
    corrected: dict[str, Any],
) -> list[dict[str, Any]]:
    before = {item["review_number"]: item for item in parent["posting_level"]}
    after = {item["review_number"]: item for item in corrected["posting_level"]}
    semantics = _semantic_payloads(config.base_replay_config, corrected["posting_level"])
    diagnostics = []
    for case in config.cases:
        old = before[case.review_number]
        new = after[case.review_number]
        semantic = semantics[case.review_number]
        matched = new["preference_assessment"]["matched_effects"]
        matched_concepts = {item["concept_id"] for item in matched}
        missed_concepts = sorted(
            set(case.expected_existing_preference_concepts) - matched_concepts
        )
        if case.unrepresented_human_factor:
            preference_failure_mode = "UNREPRESENTED_HUMAN_FACTOR"
        elif missed_concepts:
            preference_failure_mode = "EXPECTED_CONCEPT_NOT_ESTABLISHED_BY_AVAILABLE_EVIDENCE"
        elif case.expected_existing_preference_concepts:
            preference_failure_mode = "MATCHED_BUT_FROZEN_EFFECT_DID_NOT_CHANGE_DECISION"
        else:
            preference_failure_mode = "NOT_APPLICABLE"
        cluster = _cluster_for_review(corrected, case.review_number)
        classification = classify_diagnostic_case(case, old, new)
        if classification not in RESIDUAL_CLASSIFICATIONS:
            raise ReplayError("diagnostic produced an uncontrolled classification")
        diagnostics.append({
            "review_number": case.review_number,
            "classification": classification,
            "root_layer": case.root_layer,
            "market": {
                "before_status": old["market_assessment"]["status"],
                "after_status": new["market_assessment"]["status"],
                "before_reasons": old["market_assessment"]["reasons"],
                "after_reasons": new["market_assessment"]["reasons"],
                "after_evidence": new["market_assessment"]["evidence"],
                "normalization_trace": {
                    "country_evidence_was_already_available": any(
                        item.get("kind") == "location" and item.get("normalized_value")
                        for item in old["market_assessment"]["evidence"]
                    ),
                    "old_evaluator_stopped_at_work_mode_uncertainty": any(
                        item["code"] == "WORK_MODE_UNKNOWN"
                        for item in old["market_assessment"]["reasons"]
                    ),
                    "new_explicit_region_reason_applied": any(
                        item["code"] == "EXPLICIT_FOREIGN_REGION_INCOMPATIBLE"
                        for item in new["market_assessment"]["reasons"]
                    ),
                },
            },
            "cluster": {
                "cluster_id": cluster["cluster_id"],
                "review_numbers": cluster["review_numbers"],
                "preferred_review_number": cluster["preferred_review_number"],
                "is_preferred_variant": new["is_preferred_variant"],
            },
            "reused_semantic": {
                "semantic_assessment_id": new["semantic_assessment_id"],
                "cache_reused": new["cache"]["reused"],
                "dimensions": {
                    key: {
                        "score": value.get("score"),
                        "confidence": value.get("confidence"),
                        "reason": value.get("reason"),
                        "job_evidence": value.get("job_evidence", []),
                        "candidate_evidence": value.get("candidate_evidence", []),
                    }
                    for key, value in semantic.get("dimensions", {}).items()
                },
                "concepts": {
                    name: [item.get("concept_id") for item in semantic.get(name, [])]
                    for name in ("strengths", "gaps", "risks")
                },
            },
            "preferences": {
                "matched_effects": matched,
                "expected_existing_concepts": list(case.expected_existing_preference_concepts),
                "expected_existing_concepts_not_matched": missed_concepts,
                "unrepresented_human_factor": case.unrepresented_human_factor,
                "failure_mode": preference_failure_mode,
                "numeric_effect_before": old["preference_assessment"]["bounded_total_effect"],
                "numeric_effect_after": new["preference_assessment"]["bounded_total_effect"],
            },
            "recommendation_composition": {
                "before_correction": old["final_recommendation"],
                "before_market_cap": new["recommendation_before_market_policy"],
                "after_market_cap": new["market_routing"]["recommendation"],
                "after_seniority_cap": new["final_recommendation"],
                "included_in_normal_shortlist": new["include_in_normal_shortlist"],
            },
        })
    return diagnostics


def _comparison(parent: dict[str, Any], corrected: dict[str, Any]) -> dict[str, Any]:
    old = {item["review_number"]: item for item in parent["posting_level"]}
    new = {item["review_number"]: item for item in corrected["posting_level"]}
    changed_market = [key for key in old if old[key]["market_assessment"]["status"] != new[key]["market_assessment"]["status"]]
    changed_preference = [key for key in old if old[key]["preference_assessment"]["matched_effects"] != new[key]["preference_assessment"]["matched_effects"]]
    changed_decision = [
        key for key in old
        if (
            old[key]["include_in_normal_shortlist"], old[key]["final_recommendation"]
        ) != (
            new[key]["include_in_normal_shortlist"], new[key]["final_recommendation"]
        )
    ]
    parent_gates = {item["gate"]: item["status"] for item in parent["gates"]}
    corrected_gates = {item["gate"]: item["status"] for item in corrected["gates"]}
    old_opportunity = parent["metrics"]["opportunity_level"]
    new_opportunity = corrected["metrics"]["opportunity_level"]
    return {
        "market_status_distribution_before": dict(sorted(Counter(
            item["market_assessment"]["status"] for item in old.values()
        ).items())),
        "market_status_distribution_after": dict(sorted(Counter(
            item["market_assessment"]["status"] for item in new.values()
        ).items())),
        "normal_shortlist_opportunities_before": sum(
            item["include_in_normal_shortlist"] for item in parent["opportunity_level"]
        ),
        "normal_shortlist_opportunities_after": sum(
            item["include_in_normal_shortlist"] for item in corrected["opportunity_level"]
        ),
        "attention_shortlist_apply_recall_before": old_opportunity["attention_shortlist_apply_recall"],
        "attention_shortlist_apply_recall_after": new_opportunity["attention_shortlist_apply_recall"],
        "top_attention_acceptance_before": old_opportunity["top_attention_acceptance"],
        "top_attention_acceptance_after": new_opportunity["top_attention_acceptance"],
        "ranking_agreement_before": old_opportunity["ranking_agreement"],
        "ranking_agreement_after": new_opportunity["ranking_agreement"],
        "terminal_apply_acceptance_before": old_opportunity["terminal_apply_acceptance"],
        "terminal_apply_acceptance_after": new_opportunity["terminal_apply_acceptance"],
        "residual_disagreements_before": len(parent["residual_disagreements"]),
        "residual_disagreements_after": len(corrected["residual_disagreements"]),
        "market_status_changes": len(changed_market),
        "decision_changes": len(changed_decision),
        "decisions_changed_by_texas_normalization": sum(
            number == 27 for number in changed_decision
        ),
        "decisions_changed_by_preference_matching": sum(
            number in changed_preference for number in changed_decision
        ),
        "gate_transitions": {
            key: {"before": parent_gates[key], "after": corrected_gates[key]}
            for key in parent_gates
            if parent_gates[key] != corrected_gates[key]
        },
    }


def _broad_corpus_impact(base_config_path: str) -> dict[str, Any]:
    replay_config = load_replay_config(base_config_path)
    taxonomy = load_taxonomy("config/taxonomy.yaml")
    profile = load_candidate_profile("config/candidate.yaml", taxonomy)
    corrected_rules = load_market_normalization_rules("config/market_status_rules.yaml")
    baseline_rules = replace(
        corrected_rules,
        normalization_version="phase4-market-normalization-v1",
        region_countries={},
    )
    connection = sqlite3.connect(
        f"file:{Path(replay_config.baseline['database_path']).resolve()}?mode=ro&immutable=1",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    try:
        rows = _active_rows(connection)
    finally:
        connection.close()
    before: Counter[str] = Counter()
    after: Counter[str] = Counter()
    changed = 0
    assessed = 0
    for row in rows:
        if not _usable(row):
            continue
        assessed += 1
        job = _semantic_job(row["snapshot"])
        old_status = evaluate_current_candidate_market(job, profile, baseline_rules).status.value
        new_status = evaluate_current_candidate_market(job, profile, corrected_rules).status.value
        before[old_status] += 1
        after[new_status] += 1
        changed += old_status != new_status
    return {
        "assessable_active_jobs": assessed,
        "market_status_distribution_before": dict(sorted(before.items())),
        "market_status_distribution_after": dict(sorted(after.items())),
        "market_status_changes": changed,
        "external_calls": 0,
    }


def _render_diagnostic_report(artifact: dict[str, Any]) -> str:
    comparison = artifact["comparison"]
    lines = [
        f"# Phase 4 Corrected Retrospective — {artifact['run_id']}", "",
        "> Private/local diagnostic. The official v1 and SPEC-006 results remain unchanged.", "",
        "## Aggregate comparison", "",
    ]
    for key, value in comparison.items():
        lines.append(f"- {key}: `{json.dumps(value, ensure_ascii=False, sort_keys=True)}`")
    lines.extend(["", "## Residual diagnostic classifications", ""])
    for item in artifact["residual_diagnostics"]:
        lines.append(
            f"- Review {item['review_number']}: `{item['classification']}` "
            f"at `{item['root_layer']}`."
        )
    lines.extend(["", "## Integrity", ""])
    lines.append(f"- External semantic calls: {artifact['zero_call_evidence']['external_semantic_calls']}")
    lines.append(f"- Cached semantic rows reused: {artifact['zero_call_evidence']['cache_rows_compatible']}/30")
    lines.append(f"- Frozen evidence byte-identical: {artifact['immutability_check']['byte_identical']}")
    return "\n".join(lines) + "\n"


def run_residual_diagnostics(
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    *,
    run_id: str | None = None,
    write_artifact: bool = True,
) -> dict[str, Any]:
    config = load_residual_diagnostics_config(config_path)
    parent_aggregate_path = Path(config.parent_aggregate_path)
    parent_detail_path = Path(config.parent_detailed_replay_path)
    parent_aggregate_hash = _sha256(parent_aggregate_path)
    parent_detail_hash = _sha256(parent_detail_path)
    parent_aggregate = json.loads(parent_aggregate_path.read_text(encoding="utf-8"))
    parent = json.loads(parent_detail_path.read_text(encoding="utf-8"))
    expected_private_hash = parent_aggregate["privacy_boundary"]["private_artifact_hashes"]["detailed_replay_sha256"]
    if parent_detail_hash != expected_private_hash:
        raise ReplayError("parent detailed replay does not match the tracked aggregate receipt")
    if parent["run_id"] != parent_aggregate["run_id"]:
        raise ReplayError("parent replay identity does not match its aggregate receipt")

    run_id = run_id or (
        "phase4-corrected-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    )
    corrected = run_replay(
        config.base_replay_config, output_root, run_id=run_id, write_artifact=False,
    )
    corrected["experiment_id"] = config.experiment_id
    corrected["experiment_type"] = EXPERIMENT_TYPE
    corrected["residual_diagnostics_config_fingerprint"] = config.fingerprint
    corrected["parent_replay"] = {
        "experiment_id": parent["experiment_id"],
        "run_id": parent["run_id"],
        "aggregate_path": str(parent_aggregate_path),
        "aggregate_sha256": parent_aggregate_hash,
        "detailed_replay_path": str(parent_detail_path),
        "detailed_replay_sha256": parent_detail_hash,
    }
    corrected["comparison"] = _comparison(parent, corrected)
    corrected["broader_corpus_impact"] = _broad_corpus_impact(config.base_replay_config)
    corrected["residual_diagnostics"] = _diagnostic_rows(config, parent, corrected)
    corrected["residual_classification_counts"] = dict(sorted(Counter(
        item["classification"] for item in corrected["residual_diagnostics"]
    ).items()))
    corrected["correction_attribution"] = {
        "texas_normalization_decision_changes": corrected["comparison"]["decisions_changed_by_texas_normalization"],
        "preference_matching_decision_changes": corrected["comparison"]["decisions_changed_by_preference_matching"],
    }
    corrected["rule_fingerprint_comparison"] = {
        "market_rules": {
            "before": parent["frozen"]["market_rules"]["fingerprint"],
            "after": corrected["frozen"]["market_rules"]["fingerprint"],
            "changed": parent["frozen"]["market_rules"]["fingerprint"] != corrected["frozen"]["market_rules"]["fingerprint"],
        },
        "preference_matching_rules": {
            "before": parent["frozen"]["preferences"]["matching_rules_fingerprint"],
            "after": corrected["frozen"]["preferences"]["matching_rules_fingerprint"],
            "changed": parent["frozen"]["preferences"]["matching_rules_fingerprint"] != corrected["frozen"]["preferences"]["matching_rules_fingerprint"],
        },
    }
    corrected["frozen_equivalence"] = {
        "semantic": parent["frozen"]["semantic"] == corrected["frozen"]["semantic"],
        "candidate_semantic_profile": parent["frozen"]["candidate"]["semantic_profile_fingerprint"] == corrected["frozen"]["candidate"]["semantic_profile_fingerprint"],
        "scoring_preferences": parent["frozen"]["candidate"]["scoring_preference_fingerprint"] == corrected["frozen"]["candidate"]["scoring_preference_fingerprint"],
        "decision_preferences": parent["frozen"]["candidate"]["decision_preference_fingerprint"] == corrected["frozen"]["candidate"]["decision_preference_fingerprint"],
        "preference_effect_policy": parent["frozen"]["preferences"]["effect_policy_fingerprint"] == corrected["frozen"]["preferences"]["effect_policy_fingerprint"],
        "clustering_method": parent["frozen"]["clustering"]["method_version"] == corrected["frozen"]["clustering"]["method_version"],
        "seniority_policy": parent["frozen"]["seniority_guard"]["policy_fingerprint"] == corrected["frozen"]["seniority_guard"]["policy_fingerprint"],
    }
    if not all(corrected["frozen_equivalence"].values()):
        raise ReplayError("a frozen SPEC-007 policy identity changed")
    if not corrected["rule_fingerprint_comparison"]["market_rules"]["changed"]:
        raise ReplayError("corrected replay did not change the market rule fingerprint")
    if corrected["rule_fingerprint_comparison"]["preference_matching_rules"]["changed"]:
        raise ReplayError("SPEC-007 found no justified preference-matching correction")

    if write_artifact:
        run_dir = Path(output_root) / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        replay_path = run_dir / "replay.json"
        report_path = run_dir / "report.md"
        summary_path = run_dir / "aggregate_summary.json"
        replay_path.write_text(
            json.dumps(corrected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        report_path.write_text(_render_diagnostic_report(corrected), encoding="utf-8")
        summary = build_sanitized_summary(
            corrected,
            detailed_replay_sha256=_sha256(replay_path),
            detailed_report_sha256=_sha256(report_path),
        )
        summary.update({
            "schema_version": 2,
            "experiment_type": EXPERIMENT_TYPE,
            "parent_replay": {
                "experiment_id": parent["experiment_id"],
                "run_id": parent["run_id"],
                "aggregate_sha256": parent_aggregate_hash,
                "detailed_replay_sha256": parent_detail_hash,
            },
            "residual_diagnostics_config_fingerprint": config.fingerprint,
            "comparison": corrected["comparison"],
            "broader_corpus_impact": corrected["broader_corpus_impact"],
            "rule_fingerprint_comparison": corrected["rule_fingerprint_comparison"],
            "frozen_equivalence": corrected["frozen_equivalence"],
            "correction_attribution": corrected["correction_attribution"],
            "residual_classification_counts": corrected["residual_classification_counts"],
            "conclusions": [
                "The bounded Texas correction fixed the known deterministic market-normalization gap without semantic reassessment.",
                "No generic preference-matching correction was justified; frozen preference policy and matching remained unchanged.",
                "Klaxoon remains correctly uncertain under the frozen evidence and market-access policy.",
                "The remaining preference residuals require future policy representation or calibration, while the two control cases remain semantic-v1 residuals.",
                "This corrected post-hoc result does not replace official v1 or the SPEC-006 replay and requires prospective validation before promotion.",
            ],
        })
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        corrected["artifact_paths"] = {
            "private_detailed_json": str(replay_path),
            "private_detailed_report": str(report_path),
            "tracked_aggregate_summary": str(summary_path),
        }
    return corrected


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline Phase 4 residual diagnostics and corrected retrospective",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    artifact = run_residual_diagnostics(
        args.config, args.output_root, run_id=args.run_id,
        write_artifact=not args.dry_run,
    )
    print(json.dumps({
        "run_id": artifact["run_id"],
        "experiment_type": artifact["experiment_type"],
        "comparison": artifact["comparison"],
        "gates": artifact["gates"],
        "residual_classification_counts": artifact["residual_classification_counts"],
        "zero_call_evidence": artifact["zero_call_evidence"],
        "artifact_paths": artifact.get("artifact_paths"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
