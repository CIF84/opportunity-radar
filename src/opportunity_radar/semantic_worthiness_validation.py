from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import uuid
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from opportunity_radar.semantic_allocation_audit import (
    TRIAGE_STATES,
    build_presemantic_audit_population,
    load_allocation_audit_config,
)
from opportunity_radar.live_validation import observed_luna_cost


DEFAULT_CONFIG = Path("experiments/semantic_compute_worthiness_v1.yaml")
DEFAULT_DATABASE = Path("output/opportunity_radar.sqlite3")
EXPERIMENT_TYPE = "SEMANTIC_COMPUTE_WORTHINESS_HUMAN_VALIDATION"
PRIMARY_LABELS = {
    "WORTH_DEEP_ASSESSMENT",
    "NOT_WORTH_DEEP_ASSESSMENT",
    "NEED_MORE_INFO",
}


class SemanticWorthinessError(ValueError):
    pass


@dataclass(frozen=True)
class WorthinessProtocol:
    raw: dict[str, Any]
    fingerprint: str

    @property
    def experiment_id(self) -> str:
        return str(self.raw["experiment_id"])

    @property
    def version(self) -> str:
        return str(self.raw["protocol_version"])

    @property
    def sampling(self) -> dict[str, Any]:
        return self.raw["sampling"]


@dataclass
class _FlowEdge:
    to: str
    reverse: int
    capacity: int
    cost: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_unique_strings(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise SemanticWorthinessError(f"{label} must contain unique strings")
    return value


def load_worthiness_protocol(path: str | Path = DEFAULT_CONFIG) -> WorthinessProtocol:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version", "protocol_version", "experiment_id", "experiment_type",
        "allocation_config_path", "sampling", "blind_review", "human_labels",
        "metrics", "privacy", "outputs",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise SemanticWorthinessError("semantic worthiness protocol has an invalid schema")
    if raw["schema_version"] != 1 or raw["experiment_type"] != EXPERIMENT_TYPE:
        raise SemanticWorthinessError("unsupported semantic worthiness protocol identity")
    if not isinstance(raw["protocol_version"], str) or not raw["protocol_version"]:
        raise SemanticWorthinessError("protocol_version is required")
    allocation = load_allocation_audit_config(raw["allocation_config_path"])
    if allocation.experiment_id != "EXP-SEMANTIC-ALLOCATION-001":
        raise SemanticWorthinessError("protocol must freeze the SPEC-011 allocation audit")

    sampling = raw["sampling"]
    required_sampling = {
        "seed", "target", "employer_cap", "reserve_per_stratum", "stratum_order",
        "strata", "defer_shortfall_reallocation",
    }
    if not isinstance(sampling, dict) or set(sampling) != required_sampling:
        raise SemanticWorthinessError("invalid worthiness sampling schema")
    order = _require_unique_strings(sampling["stratum_order"], "stratum_order")
    if set(order) != TRIAGE_STATES or set(sampling["strata"]) != TRIAGE_STATES:
        raise SemanticWorthinessError("sampling strata must match the frozen triage states")
    for field in ("target", "employer_cap", "reserve_per_stratum"):
        value = sampling[field]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise SemanticWorthinessError(f"sampling.{field} must be a positive integer")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in sampling["strata"].values()
    ):
        raise SemanticWorthinessError("stratum targets must be non-negative integers")
    if sum(sampling["strata"].values()) != sampling["target"]:
        raise SemanticWorthinessError("stratum targets must sum to sampling.target")
    if sampling["defer_shortfall_reallocation"] != "SEMANTIC_OPTIONAL":
        raise SemanticWorthinessError("DEFER shortfall must reallocate to OPTIONAL")

    labels = raw["human_labels"]
    if not isinstance(labels, dict) or set(labels) != {"primary", "optional_reasons"}:
        raise SemanticWorthinessError("invalid human label schema")
    if set(_require_unique_strings(labels["primary"], "primary labels")) != PRIMARY_LABELS:
        raise SemanticWorthinessError("primary labels do not match the frozen vocabulary")
    _require_unique_strings(labels["optional_reasons"], "optional reasons")

    gates = raw.get("metrics", {}).get("gates")
    expected_gates = {
        "defer_not_worth_safety_minimum", "defer_worth_maximum",
        "priority_worth_precision_minimum", "need_more_info_maximum",
        "catastrophic_employer_blind_spot",
    }
    if not isinstance(gates, dict) or set(gates) != expected_gates:
        raise SemanticWorthinessError("invalid metric gates")
    for field in (
        "defer_not_worth_safety_minimum", "priority_worth_precision_minimum",
        "need_more_info_maximum",
    ):
        if not 0 <= float(gates[field]) <= 1:
            raise SemanticWorthinessError(f"{field} must be in [0, 1]")
    if not isinstance(gates["defer_worth_maximum"], int):
        raise SemanticWorthinessError("defer_worth_maximum must be an integer")
    blind_spot = gates["catastrophic_employer_blind_spot"]
    if not isinstance(blind_spot, dict) or set(blind_spot) != {
        "minimum_adjudicated_defer", "worth_count_minimum", "worth_rate_minimum",
    }:
        raise SemanticWorthinessError("invalid employer blind-spot rule")
    excerpt = raw.get("blind_review", {}).get("description_excerpt_characters")
    if not isinstance(excerpt, int) or isinstance(excerpt, bool) or excerpt < 300:
        raise SemanticWorthinessError("blind review excerpt length is invalid")
    if raw["privacy"] != {
        "detailed_artifacts": "PRIVATE_LOCAL",
        "human_judgments": "PRIVATE_LOCAL_APPEND_ONLY",
        "aggregate_summary": "REPOSITORY_SAFE",
    }:
        raise SemanticWorthinessError("invalid worthiness privacy policy")
    if set(raw["outputs"]) != {"root", "judgments", "replacements"}:
        raise SemanticWorthinessError("invalid worthiness output paths")
    return WorthinessProtocol(raw=raw, fingerprint=_digest(raw))


def _stable_key(seed: str, *parts: str) -> str:
    return hashlib.sha256(":".join((seed, *parts)).encode()).hexdigest()


def _selection_projection(population: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Project away cache and semantic fields before selection."""
    projected: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in population:
        cluster_id = str(row["cluster_id"])
        if cluster_id in seen:
            raise SemanticWorthinessError(f"duplicate cluster_id: {cluster_id}")
        seen.add(cluster_id)
        state = str(row["presemantic_triage"]["state"])
        if state not in TRIAGE_STATES:
            raise SemanticWorthinessError(f"invalid triage state: {state}")
        projected.append({
            "cluster_id": cluster_id,
            "company_id": str(row["company_id"]),
            "stratum": state,
        })
    return projected


def _balanced_take(
    rows: list[dict[str, str]], count: int, seed: str, stratum: str,
    employer_counts: Counter[str] | None = None, cap: int | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    employer_counts = employer_counts if employer_counts is not None else Counter()
    queues: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        queues[row["company_id"]].append(row)
    for company, values in queues.items():
        values.sort(key=lambda item: _stable_key(seed, stratum, company, item["cluster_id"]))
    companies = sorted(queues, key=lambda company: _stable_key(seed, stratum, company))
    selected: list[dict[str, str]] = []
    relaxations: list[dict[str, Any]] = []
    effective_cap = cap
    while len(selected) < count:
        progress = False
        for company in companies:
            if len(selected) >= count:
                break
            if not queues[company]:
                continue
            if effective_cap is not None and employer_counts[company] >= effective_cap:
                continue
            selected.append(queues[company].pop(0))
            employer_counts[company] += 1
            progress = True
        if progress:
            continue
        remaining = sum(len(values) for values in queues.values())
        if not remaining:
            break
        if effective_cap is None:
            break
        prior = effective_cap
        effective_cap += 1
        relaxations.append({
            "stratum": stratum,
            "from_cap": prior,
            "to_cap": effective_cap,
            "selected_before_relaxation": len(selected),
        })
    return selected, relaxations


def _solve_global_employer_cap(
    by_stratum: dict[str, list[dict[str, str]]], targets: dict[str, int],
    cap: int, seed: str, stratum_order: list[str],
) -> tuple[int, dict[tuple[str, str], int]]:
    """Solve the stratum quotas jointly so abundant strata cannot consume scarce capacity."""
    source, sink = "@source", "@sink"
    capacity: dict[tuple[str, str], int] = {}
    original: dict[tuple[str, str], int] = {}
    neighbors: dict[str, list[str]] = defaultdict(list)

    def add_edge(left: str, right: str, value: int) -> None:
        capacity[(left, right)] = value
        capacity[(right, left)] = 0
        original[(left, right)] = value
        neighbors[left].append(right)
        neighbors[right].append(left)

    companies = sorted({row["company_id"] for rows in by_stratum.values() for row in rows})
    for stratum in stratum_order:
        stratum_node = f"stratum:{stratum}"
        add_edge(source, stratum_node, targets[stratum])
        available = Counter(row["company_id"] for row in by_stratum[stratum])
        ordered_companies = sorted(
            available, key=lambda company: _stable_key(seed, stratum, company),
        )
        for company in ordered_companies:
            add_edge(
                stratum_node, f"company:{company}",
                min(available[company], targets[stratum], cap),
            )
    for company in sorted(companies, key=lambda value: _stable_key(seed, "employer", value)):
        add_edge(f"company:{company}", sink, cap)

    flow = 0
    while True:
        parent: dict[str, str | None] = {source: None}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for neighbor in neighbors[node]:
                if neighbor not in parent and capacity[(node, neighbor)] > 0:
                    parent[neighbor] = node
                    queue.append(neighbor)
                    if neighbor == sink:
                        break
            if sink in parent:
                break
        if sink not in parent:
            break
        amount = 10**9
        node = sink
        while parent[node] is not None:
            prior = parent[node]
            amount = min(amount, capacity[(prior, node)])
            node = prior
        node = sink
        while parent[node] is not None:
            prior = parent[node]
            capacity[(prior, node)] -= amount
            capacity[(node, prior)] += amount
            node = prior
        flow += amount

    allocation: dict[tuple[str, str], int] = {}
    for stratum in stratum_order:
        left = f"stratum:{stratum}"
        for company in companies:
            edge = (left, f"company:{company}")
            if edge in original:
                used = original[edge] - capacity[edge]
                if used:
                    allocation[(stratum, company)] = used
    return flow, allocation


def _balanced_allocation_at_cap(
    by_stratum: dict[str, list[dict[str, str]]], targets: dict[str, int],
    cap: int, seed: str, stratum_order: list[str],
) -> dict[tuple[str, str], int]:
    """Minimize global and within-stratum concentration at a proven feasible cap."""
    source, sink = "@source", "@sink"
    graph: dict[str, list[_FlowEdge]] = defaultdict(list)
    tracked: dict[tuple[str, str, int], _FlowEdge] = {}

    def add_edge(left: str, right: str, capacity: int, cost: int) -> _FlowEdge:
        forward = _FlowEdge(right, len(graph[right]), capacity, cost)
        reverse = _FlowEdge(left, len(graph[left]), 0, -cost)
        graph[left].append(forward)
        graph[right].append(reverse)
        return forward

    companies = sorted({row["company_id"] for rows in by_stratum.values() for row in rows})
    for stratum in stratum_order:
        stratum_node = f"stratum:{stratum}"
        add_edge(source, stratum_node, targets[stratum], 0)
        available = Counter(row["company_id"] for row in by_stratum[stratum])
        company_rank = {
            company: rank for rank, company in enumerate(sorted(
                available, key=lambda value: _stable_key(seed, stratum, value),
            ))
        }
        for company, count in available.items():
            for slot in range(min(count, targets[stratum], cap)):
                unit = f"unit:{stratum}:{company}:{slot}"
                # Convex slot costs prefer breadth; the stable rank breaks ties.
                add_edge(stratum_node, unit, 1, slot * 1_000 + company_rank[company])
                tracked[(stratum, company, slot)] = add_edge(
                    unit, f"company:{company}", 1, 0,
                )
    global_rank = {
        company: rank for rank, company in enumerate(sorted(
            companies, key=lambda value: _stable_key(seed, "employer", value),
        ))
    }
    for company in companies:
        for slot in range(cap):
            unit = f"global:{company}:{slot}"
            add_edge(
                f"company:{company}", unit, 1,
                slot * 100_000 + global_rank[company],
            )
            add_edge(unit, sink, 1, 0)

    required = sum(targets.values())
    flow = 0
    while flow < required:
        distance = {node: 10**18 for node in graph}
        distance[source] = 0
        parent: dict[str, tuple[str, int]] = {}
        queue = deque([source])
        queued = {source}
        while queue:
            node = queue.popleft()
            queued.discard(node)
            for index, edge in enumerate(graph[node]):
                candidate = distance[node] + edge.cost
                if edge.capacity > 0 and candidate < distance.get(edge.to, 10**18):
                    distance[edge.to] = candidate
                    parent[edge.to] = (node, index)
                    if edge.to not in queued:
                        queue.append(edge.to)
                        queued.add(edge.to)
        if sink not in parent:
            raise SemanticWorthinessError("balanced allocation failed after cap feasibility")
        node = sink
        while node != source:
            prior, index = parent[node]
            edge = graph[prior][index]
            edge.capacity -= 1
            graph[node][edge.reverse].capacity += 1
            node = prior
        flow += 1

    allocation: Counter[tuple[str, str]] = Counter()
    for (stratum, company, _), edge in tracked.items():
        if edge.capacity == 0:
            allocation[(stratum, company)] += 1
    return dict(allocation)


def select_worthiness_sample(
    population: list[dict[str, Any]], protocol: WorthinessProtocol,
) -> dict[str, Any]:
    projected = _selection_projection(population)
    by_stratum = {
        stratum: [row for row in projected if row["stratum"] == stratum]
        for stratum in protocol.sampling["stratum_order"]
    }
    targets = dict(protocol.sampling["strata"])
    defer = "SEMANTIC_DEFER"
    defer_shortfall = max(0, targets[defer] - len(by_stratum[defer]))
    if defer_shortfall:
        targets[defer] -= defer_shortfall
        targets[protocol.sampling["defer_shortfall_reallocation"]] += defer_shortfall

    seed = str(protocol.sampling["seed"])
    target_total = sum(targets.values())
    effective_cap = int(protocol.sampling["employer_cap"])
    relaxations: list[dict[str, Any]] = []
    while True:
        filled, allocation = _solve_global_employer_cap(
            by_stratum, targets, effective_cap, seed,
            list(protocol.sampling["stratum_order"]),
        )
        if filled == target_total:
            break
        prior = effective_cap
        effective_cap += 1
        relaxations.append({
            "from_cap": prior,
            "to_cap": effective_cap,
            "maximum_fill_at_prior_cap": filled,
        })
        if effective_cap > target_total:
            raise SemanticWorthinessError("cannot fill frozen sample from available strata")

    allocation = _balanced_allocation_at_cap(
        by_stratum, targets, effective_cap, seed,
        list(protocol.sampling["stratum_order"]),
    )

    selected: list[dict[str, str]] = []
    for stratum in protocol.sampling["stratum_order"]:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in by_stratum[stratum]:
            grouped[row["company_id"]].append(row)
        for company, count in sorted(
            ((company, count) for (state, company), count in allocation.items() if state == stratum),
            key=lambda item: _stable_key(seed, stratum, item[0]),
        ):
            grouped[company].sort(
                key=lambda row: _stable_key(seed, stratum, company, row["cluster_id"])
            )
            selected.extend(grouped[company][:count])
    employer_counts = Counter(item["company_id"] for item in selected)

    selected_ids = {item["cluster_id"] for item in selected}
    reserves: dict[str, list[dict[str, Any]]] = {}
    for stratum in protocol.sampling["stratum_order"]:
        candidates = [
            row for row in by_stratum[stratum] if row["cluster_id"] not in selected_ids
        ]
        values, _ = _balanced_take(
            candidates, int(protocol.sampling["reserve_per_stratum"]),
            f"{seed}:reserve", stratum,
        )
        reserves[stratum] = [dict(item, reserve_order=index) for index, item in enumerate(values, 1)]

    selected.sort(key=lambda item: _stable_key(f"{seed}:review", item["cluster_id"]))
    selected = [dict(item, review_number=index) for index, item in enumerate(selected, 1)]
    if len(selected) != protocol.sampling["target"]:
        raise SemanticWorthinessError("selected sample does not match frozen target")
    return {
        "selected": selected,
        "reserves": reserves,
        "requested_strata": dict(protocol.sampling["strata"]),
        "effective_strata": targets,
        "defer_shortfall": defer_shortfall,
        "employer_cap_requested": protocol.sampling["employer_cap"],
        "employer_cap_effective": effective_cap,
        "employer_counts": dict(sorted(employer_counts.items())),
        "cap_relaxations": relaxations,
        "selection_fingerprint": _digest([
            (item["review_number"], item["cluster_id"], item["stratum"])
            for item in selected
        ]),
    }


def _evidence_missing(row: dict[str, Any]) -> list[str]:
    missing = []
    if not row.get("title"):
        missing.append("title")
    if not row.get("description"):
        missing.append("description")
    if not row.get("canonical_url"):
        missing.append("source_link")
    if not row.get("locations"):
        missing.append("location")
    if row.get("work_mode") in {None, "", "unspecified"}:
        missing.append("work_mode")
    return missing


def _private_review_item(
    selection: dict[str, Any], row: dict[str, Any], excerpt_characters: int,
) -> dict[str, Any]:
    description = (row.get("description") or "").strip()
    excerpt = description[:excerpt_characters]
    if len(description) > excerpt_characters:
        excerpt = excerpt.rstrip() + "…"
    return {
        **selection,
        "cluster_fingerprint": row["cluster_fingerprint"],
        "company_name": row.get("company_name"),
        "title": row.get("title"),
        "locations": row.get("locations", []),
        "work_mode": row.get("work_mode"),
        "employment_type": row.get("employment_type"),
        "department": row.get("department"),
        "market_status": row.get("market_status"),
        "market_evidence": row.get("market_assessment"),
        "description_excerpt": excerpt,
        "canonical_url": row.get("canonical_url"),
        "evidence_missing": _evidence_missing(row),
        "presemantic_evidence": row["presemantic_triage"],
        "preferred_variant_job_instance_id": row.get("preferred_variant_job_instance_id"),
        "member_job_instance_ids": row.get("member_job_instance_ids", []),
    }


def _location_text(item: dict[str, Any]) -> str:
    values = []
    for location in item.get("locations", []):
        text = location.get("raw") or ", ".join(
            str(location.get(field)) for field in ("city", "region", "country")
            if location.get(field)
        )
        if text:
            values.append(text)
    return "; ".join(values) or "Not stated"


def render_blind_review(manifest: dict[str, Any], items: list[dict[str, Any]] | None = None) -> str:
    items = items or manifest["sample"]["selected"]
    lines = [
        f"# Semantic Compute-Worthiness Review — {manifest['preparation_id']}", "",
        "> Private human-review evidence. Do not commit this file.", "",
        "For each opportunity answer:", "",
        "> Would it be worth spending deeper AI reasoning on this opportunity before deciding whether it deserves your attention?",
        "",
        "Labels: `WORTH_DEEP_ASSESSMENT`, `NOT_WORTH_DEEP_ASSESSMENT`, or `NEED_MORE_INFO`.",
        "This is not an APPLY/DONT_APPLY decision.", "",
    ]
    for item in sorted(items, key=lambda value: value["review_number"]):
        lines.extend([
            f"## Review {item['review_number']}", "",
            f"Employer: {item.get('company_name') or 'Not stated'}", "",
            f"Role: {item.get('title') or 'Not stated'}", "",
            f"Location: {_location_text(item)}", "",
            f"Work mode: {item.get('work_mode') or 'unspecified'}", "",
            f"Employment type: {item.get('employment_type') or 'Not stated'}", "",
            f"Department: {item.get('department') or 'Not stated'}", "",
            f"Practical market evidence: {item.get('market_status') or 'UNKNOWN'}",
            "",
            "Description/excerpt:", "",
            item.get("description_excerpt") or "Not available.", "",
            f"Source: {item.get('canonical_url') or 'Not available'}", "",
            "Evidence gaps: " + (", ".join(item.get("evidence_missing", [])) or "None identified"),
            "",
            "Label: ____________________", "Reason(s), optional: ____________________",
            "Private note, optional: ____________________", "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def _coverage(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    checks = {
        "title": lambda row: bool(row.get("title")),
        "description_excerpt": lambda row: bool(row.get("description_excerpt")),
        "location": lambda row: bool(row.get("locations")),
        "work_mode": lambda row: row.get("work_mode") not in {None, "", "unspecified"},
        "employment_type": lambda row: bool(row.get("employment_type")),
        "department": lambda row: bool(row.get("department")),
        "source_link": lambda row: bool(row.get("canonical_url")),
        "market_status": lambda row: row.get("market_status") in {"IN_SCOPE", "UNCERTAIN", "OUT_OF_SCOPE"},
    }
    total = len(items)
    return {
        key: {
            "available": sum(bool(check(row)) for row in items),
            "total": total,
            "coverage": round(sum(bool(check(row)) for row in items) / total, 6) if total else 0.0,
        }
        for key, check in checks.items()
    }


def _git_provenance(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True,
        ).stdout.strip()
    status = run("status", "--porcelain")
    return {
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(status),
        "worktree_status_fingerprint": hashlib.sha256(status.encode()).hexdigest(),
    }


def _write_immutable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(content)


def prepare_worthiness_validation(
    database: str | Path = DEFAULT_DATABASE,
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path | None = None,
    *,
    preparation_id: str | None = None,
) -> dict[str, Any]:
    protocol = load_worthiness_protocol(config_path)
    allocation_config = load_allocation_audit_config(protocol.raw["allocation_config_path"])
    database = Path(database)
    database_hash_before = _sha256_file(database)
    database_mtime_before = database.stat().st_mtime_ns
    bundle = build_presemantic_audit_population(
        protocol.raw["allocation_config_path"], database,
    )
    population = bundle["routed_population"]
    allocation_protocol = bundle["protocol"]
    profile = bundle["context"]["profile"]
    cost = observed_luna_cost(allocation_protocol.raw["roi_results_path"])
    selection = select_worthiness_sample(population, protocol)
    by_id = {row["cluster_id"]: row for row in population}
    excerpt = int(protocol.raw["blind_review"]["description_excerpt_characters"])
    selected = [
        _private_review_item(item, by_id[item["cluster_id"]], excerpt)
        for item in selection["selected"]
    ]
    reserves = {
        stratum: [
            _private_review_item(item, by_id[item["cluster_id"]], excerpt)
            for item in values
        ]
        for stratum, values in selection["reserves"].items()
    }
    preparation_id = preparation_id or (
        "semantic-worthiness-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
        + uuid.uuid4().hex[:8]
    )
    root = Path(output_root or protocol.raw["outputs"]["root"])
    directory = root / preparation_id
    manifest = {
        "schema_version": 1,
        "artifact_type": "PRIVATE_SEMANTIC_COMPUTE_WORTHINESS_SAMPLE",
        "preparation_id": preparation_id,
        "experiment_id": protocol.experiment_id,
        "protocol_version": protocol.version,
        "protocol_fingerprint": protocol.fingerprint,
        "created_at": utc_now(),
        "question": "Would deeper AI reasoning be worth spending before deciding attention?",
        "human_labels": protocol.raw["human_labels"],
        "sample": {
            **{key: value for key, value in selection.items() if key not in {"selected", "reserves"}},
            "selected": selected,
            "reserves": reserves,
        },
        "population": {
            "routed_clusters": len(population),
            "triage_distribution": dict(sorted(Counter(
                row["presemantic_triage"]["state"] for row in population
            ).items())),
            "projected_cache_misses_by_stratum": dict(sorted(Counter(
                row["presemantic_triage"]["state"]
                for row in population if row["semantic_cache_status"] == "SEMANTIC_CACHE_MISS"
            ).items())),
            "estimated_cost_per_cache_miss_usd": cost["estimated_cost_per_cache_miss_usd"],
        },
        "historical_exclusion": bundle["historical_exclusion"],
        "configuration": {
            "audit_fingerprint": allocation_config.fingerprint,
            "prospective_protocol_fingerprint": allocation_protocol.fingerprint,
            "candidate_full_profile_fingerprint": profile.full_profile_fingerprint,
            "candidate_semantic_profile_fingerprint": profile.semantic_profile_fingerprint,
            "market_policy_fingerprint": profile.market_access_policy_fingerprint,
            "decision_preference_fingerprint": profile.decision_preference_fingerprint,
            "worthiness_protocol_fingerprint": protocol.fingerprint,
            "allocation_config_fingerprint": allocation_config.fingerprint,
        },
        "integrity": {
            "database_sha256": database_hash_before,
            "external_semantic_calls": 0,
            "live_source_calls": 0,
            "prospective_batches_created": 0,
            "human_judgments_created": 0,
        },
        "privacy": protocol.raw["privacy"],
    }
    manifest_path = directory / "manifest.json"
    review_path = directory / "blind_review.md"
    _write_immutable(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _write_immutable(review_path, render_blind_review(manifest))
    database_hash_after = _sha256_file(database)
    if (
        database_hash_after != database_hash_before
        or database.stat().st_mtime_ns != database_mtime_before
    ):
        raise SemanticWorthinessError("preparation mutated the operational database")

    selected_counts = dict(sorted(Counter(item["stratum"] for item in selected).items()))
    reserve_counts = {key: len(value) for key, value in sorted(reserves.items())}
    aggregate = {
        "schema_version": 1,
        "artifact_type": "REPOSITORY_SAFE_SEMANTIC_WORTHINESS_PREPARATION",
        "preparation_id": preparation_id,
        "experiment_id": protocol.experiment_id,
        "protocol_version": protocol.version,
        "created_at": manifest["created_at"],
        "status": "PREPARED_AWAITING_HUMAN_REVIEW",
        "sample": {
            "target": protocol.sampling["target"],
            "selected_count": len(selected),
            "selected_stratum_counts": selected_counts,
            "reserve_counts": reserve_counts,
            "defer_shortfall": selection["defer_shortfall"],
            "employer_count": len(selection["employer_counts"]),
            "employer_distribution": selection["employer_counts"],
            "employer_cap_requested": selection["employer_cap_requested"],
            "employer_cap_effective": selection["employer_cap_effective"],
            "cap_relaxations": selection["cap_relaxations"],
            "selection_fingerprint": selection["selection_fingerprint"],
            "market_status_distribution": dict(sorted(Counter(
                item["market_status"] for item in selected
            ).items())),
            "evidence_coverage": _coverage(selected),
        },
        "population": manifest["population"],
        "historical_exclusion": bundle["historical_exclusion"],
        "configuration": manifest["configuration"],
        "provenance": {
            "git": _git_provenance(Path.cwd()),
            "database_sha256": database_hash_before,
            "allocation_source_experiment_id": allocation_config.experiment_id,
            "private_manifest_sha256": _sha256_file(manifest_path),
            "private_blind_review_sha256": _sha256_file(review_path),
        },
        "integrity": {
            "database_unchanged": True,
            "external_semantic_calls": 0,
            "live_source_calls": 0,
            "prospective_batches_created": 0,
            "human_judgments_created": 0,
            "blind_review_hides_triage": True,
            "selection_is_cache_blind": True,
        },
        "privacy": {
            "private_manifest": "PRIVATE_LOCAL",
            "blind_review": "PRIVATE_LOCAL",
            "human_judgments": "PRIVATE_LOCAL_APPEND_ONLY",
            "aggregate_summary": "REPOSITORY_SAFE",
        },
        "limitations": [
            "This is a bounded exploratory learning sample, not product validation.",
            "The triage contract remains unpromoted and is hidden during initial review.",
            "Sample selection ignores semantic cache state and semantic outputs.",
            "No compute-worthiness labels or conclusions exist before human review.",
        ],
    }
    aggregate_path = directory / "aggregate_summary.json"
    _write_immutable(aggregate_path, json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n")
    return {
        "preparation_id": preparation_id,
        "manifest": manifest,
        "aggregate": aggregate,
        "private_manifest_path": str(manifest_path),
        "private_blind_review_path": str(review_path),
        "aggregate_summary_path": str(aggregate_path),
    }


def load_preparation(output_root: str | Path, preparation_id: str) -> dict[str, Any]:
    path = Path(output_root) / preparation_id / "manifest.json"
    if not path.exists():
        raise SemanticWorthinessError(f"preparation not found: {preparation_id}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("preparation_id") != preparation_id:
        raise SemanticWorthinessError("preparation identity mismatch")
    return value


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _current_append_only(
    records: list[dict[str, Any]], preparation_id: str, id_field: str,
) -> dict[str, dict[str, Any]]:
    relevant = [row for row in records if row.get("preparation_id") == preparation_id]
    by_id = {row["record_id"]: row for row in relevant}
    superseded: set[str] = set()
    for row in relevant:
        previous = row.get("supersedes_record_id")
        if not previous:
            continue
        if previous not in by_id:
            raise SemanticWorthinessError(f"superseded record not found: {previous}")
        old = by_id[previous]
        if old[id_field] != row[id_field]:
            raise SemanticWorthinessError("record may supersede only the same identity")
        if previous in superseded:
            raise SemanticWorthinessError("record supersession cannot branch")
        superseded.add(previous)
    current: dict[str, dict[str, Any]] = {}
    for row in relevant:
        if row["record_id"] in superseded:
            continue
        identity = row[id_field]
        if identity in current:
            raise SemanticWorthinessError("append-only history has multiple current records")
        current[identity] = row
    return current


def _append_jsonl(path: str | Path, value: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def current_replacements(records: list[dict[str, Any]], preparation_id: str) -> list[dict[str, Any]]:
    relevant = [row for row in records if row.get("preparation_id") == preparation_id]
    relevant.sort(key=lambda row: row["replaced_at"])
    return relevant


def effective_selected_items(
    manifest: dict[str, Any], replacements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_review = {
        int(item["review_number"]): dict(item) for item in manifest["sample"]["selected"]
    }
    reserves = {
        item["cluster_id"]: item
        for values in manifest["sample"]["reserves"].values() for item in values
    }
    for row in current_replacements(replacements, manifest["preparation_id"]):
        review = int(row["review_number"])
        current = by_review.get(review)
        if current is None or current["cluster_id"] != row["replaced_cluster_id"]:
            raise SemanticWorthinessError("invalid replacement chain")
        replacement = reserves.get(row["replacement_cluster_id"])
        if replacement is None or replacement["stratum"] != current["stratum"]:
            raise SemanticWorthinessError("replacement must use a frozen same-stratum reserve")
        by_review[review] = dict(replacement, review_number=review)
    return [by_review[index] for index in sorted(by_review)]


def append_replacement(
    manifest: dict[str, Any], replacements_path: str | Path, judgments_path: str | Path,
    review_number: int, reason: str,
) -> dict[str, Any]:
    replacements = load_jsonl(replacements_path)
    effective = {item["review_number"]: item for item in effective_selected_items(manifest, replacements)}
    current = effective.get(review_number)
    if current is None:
        raise SemanticWorthinessError(f"review number not found: {review_number}")
    judgments = _current_append_only(
        load_jsonl(judgments_path), manifest["preparation_id"], "cluster_id",
    )
    if current["cluster_id"] in judgments:
        raise SemanticWorthinessError("cannot replace an opportunity after judgment")
    used = {
        row["replacement_cluster_id"] for row in replacements
        if row.get("preparation_id") == manifest["preparation_id"]
    }
    reserves = manifest["sample"]["reserves"].get(current["stratum"], [])
    replacement = next((row for row in reserves if row["cluster_id"] not in used), None)
    if replacement is None:
        raise SemanticWorthinessError("no frozen same-stratum reserve remains")
    value = {
        "record_id": str(uuid.uuid4()),
        "preparation_id": manifest["preparation_id"],
        "review_number": review_number,
        "stratum": current["stratum"],
        "replaced_cluster_id": current["cluster_id"],
        "replacement_cluster_id": replacement["cluster_id"],
        "reason": reason,
        "replaced_at": utc_now(),
        "supersedes_record_id": None,
    }
    _append_jsonl(replacements_path, value)
    return value


def append_worthiness_judgment(
    manifest: dict[str, Any], judgments_path: str | Path,
    replacements_path: str | Path, label: str, *, review_number: int | None = None,
    cluster_id: str | None = None, reasons: list[str] | None = None,
    note: str | None = None, supersedes: str | None = None,
) -> dict[str, Any]:
    if (review_number is None) == (cluster_id is None):
        raise SemanticWorthinessError("specify exactly one of review_number or cluster_id")
    label = label.upper()
    if label not in PRIMARY_LABELS:
        raise SemanticWorthinessError(f"invalid worthiness label: {label}")
    reasons = reasons or []
    allowed = set(manifest["human_labels"]["optional_reasons"])
    unknown = set(reasons) - allowed
    if unknown:
        raise SemanticWorthinessError(f"invalid worthiness reasons: {sorted(unknown)}")
    items = effective_selected_items(manifest, load_jsonl(replacements_path))
    matches = [
        item for item in items
        if (review_number is not None and item["review_number"] == review_number)
        or (cluster_id is not None and item["cluster_id"] == cluster_id)
    ]
    if len(matches) != 1:
        raise SemanticWorthinessError("review identity is missing or ambiguous")
    selected = matches[0]
    records = load_jsonl(judgments_path)
    current = _current_append_only(records, manifest["preparation_id"], "cluster_id")
    existing = current.get(selected["cluster_id"])
    if existing and not supersedes:
        raise SemanticWorthinessError(
            f"current judgment exists; supersede {existing['record_id']}"
        )
    if supersedes and (not existing or existing["record_id"] != supersedes):
        raise SemanticWorthinessError("supersedes must reference the current judgment")
    value = {
        "record_id": str(uuid.uuid4()),
        "preparation_id": manifest["preparation_id"],
        "experiment_id": manifest["experiment_id"],
        "protocol_fingerprint": manifest["protocol_fingerprint"],
        "selection_fingerprint": manifest["sample"]["selection_fingerprint"],
        "review_number": selected["review_number"],
        "cluster_id": selected["cluster_id"],
        "cluster_fingerprint": selected["cluster_fingerprint"],
        "label": label,
        "reasons": reasons,
        "note": note,
        "reviewed_at": utc_now(),
        "supersedes_record_id": supersedes,
    }
    _append_jsonl(judgments_path, value)
    return value


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def calculate_worthiness_metrics(
    manifest: dict[str, Any], judgments: list[dict[str, Any]],
    replacements: list[dict[str, Any]], protocol: WorthinessProtocol,
) -> dict[str, Any]:
    items = effective_selected_items(manifest, replacements)
    current = _current_append_only(judgments, manifest["preparation_id"], "cluster_id")
    reviewed = [(item, current[item["cluster_id"]]) for item in items if item["cluster_id"] in current]
    by_stratum: dict[str, dict[str, Any]] = {}
    for stratum in protocol.sampling["stratum_order"]:
        rows = [judgment for item, judgment in reviewed if item["stratum"] == stratum]
        counts = Counter(row["label"] for row in rows)
        adjudicated = counts["WORTH_DEEP_ASSESSMENT"] + counts["NOT_WORTH_DEEP_ASSESSMENT"]
        by_stratum[stratum] = {
            "reviewed": len(rows),
            "adjudicated": adjudicated,
            "labels": {label: counts[label] for label in sorted(PRIMARY_LABELS)},
            "worthiness_rate": _ratio(counts["WORTH_DEEP_ASSESSMENT"], adjudicated),
            "not_worth_rate": _ratio(counts["NOT_WORTH_DEEP_ASSESSMENT"], adjudicated),
            "need_more_info_rate": _ratio(counts["NEED_MORE_INFO"], len(rows)),
        }
    total_counts = Counter(row["label"] for _, row in reviewed)
    total_worth = total_counts["WORTH_DEEP_ASSESSMENT"]
    gates_config = protocol.raw["metrics"]["gates"]
    complete = len(reviewed) == len(items)
    priority = by_stratum["SEMANTIC_PRIORITY"]
    defer = by_stratum["SEMANTIC_DEFER"]

    defer_by_employer: dict[str, Counter[str]] = defaultdict(Counter)
    for item, judgment in reviewed:
        if item["stratum"] == "SEMANTIC_DEFER" and judgment["label"] != "NEED_MORE_INFO":
            defer_by_employer[item["company_id"]][judgment["label"]] += 1
    blind_rule = gates_config["catastrophic_employer_blind_spot"]
    blind_spots = []
    for company, counts in defer_by_employer.items():
        adjudicated = sum(counts.values())
        worth = counts["WORTH_DEEP_ASSESSMENT"]
        if (
            adjudicated >= int(blind_rule["minimum_adjudicated_defer"])
            and worth >= int(blind_rule["worth_count_minimum"])
            and worth / adjudicated >= float(blind_rule["worth_rate_minimum"])
        ):
            blind_spots.append(company)

    def gate(passed: bool) -> str:
        return "PASS" if complete and passed else "FAIL" if complete else "NOT_READY"

    need_rate = _ratio(total_counts["NEED_MORE_INFO"], len(reviewed))
    gate_results = {
        "defer_safety": gate(
            defer["not_worth_rate"] is not None
            and defer["not_worth_rate"] >= float(gates_config["defer_not_worth_safety_minimum"])
        ),
        "defer_worth_count": gate(
            defer["labels"]["WORTH_DEEP_ASSESSMENT"] <= int(gates_config["defer_worth_maximum"])
        ),
        "priority_precision": gate(
            priority["worthiness_rate"] is not None
            and priority["worthiness_rate"] >= float(gates_config["priority_worth_precision_minimum"])
        ),
        "information_sufficiency": gate(
            need_rate is not None and need_rate <= float(gates_config["need_more_info_maximum"])
        ),
        "employer_blind_spot": gate(not blind_spots),
    }

    population = manifest["population"]
    misses = population["projected_cache_misses_by_stratum"]
    cost = float(population["estimated_cost_per_cache_miss_usd"])
    policies = {
        "PRIORITY_ONLY": {"SEMANTIC_PRIORITY"},
        "PRIORITY_PLUS_OPTIONAL": {"SEMANTIC_PRIORITY", "SEMANTIC_OPTIONAL"},
        "ALL_EXCEPT_DEFER": {"SEMANTIC_PRIORITY", "SEMANTIC_OPTIONAL"},
        "ALL_ROUTED": set(TRIAGE_STATES),
    }
    economics = {}
    for name, strata in policies.items():
        calls = sum(int(misses.get(stratum, 0)) for stratum in strata)
        assessed = [(item, row) for item, row in reviewed if item["stratum"] in strata]
        assessed_adjudicated = [row for _, row in assessed if row["label"] != "NEED_MORE_INFO"]
        assessed_worth = sum(
            row["label"] == "WORTH_DEEP_ASSESSMENT" for _, row in assessed
        )
        economics[name] = {
            "current_population_projected_calls": calls,
            "current_population_projected_cost_usd": round(calls * cost, 8),
            "sample_worth_recall": _ratio(assessed_worth, total_worth),
            "sample_worth_precision": _ratio(assessed_worth, len(assessed_adjudicated)),
        }
    return {
        "status": "COMPLETE" if complete else "IN_PROGRESS",
        "reviewed": len(reviewed),
        "target": len(items),
        "replacement_count": len(current_replacements(replacements, manifest["preparation_id"])),
        "labels": {label: total_counts[label] for label in sorted(PRIMARY_LABELS)},
        "need_more_info_rate": need_rate,
        "by_stratum": by_stratum,
        "priority_precision": priority["worthiness_rate"],
        "defer_safety": defer["not_worth_rate"],
        "defer_worth_count": defer["labels"]["WORTH_DEEP_ASSESSMENT"],
        "employer_blind_spot_count": len(blind_spots),
        "employer_blind_spots_private": sorted(blind_spots),
        "gates": gate_results,
        "all_directional_gates_pass": complete and all(value == "PASS" for value in gate_results.values()),
        "counterfactual_economics": economics,
        "promotion_note": "Passing directional gates is necessary but not sufficient for runtime promotion.",
    }


def render_private_report(manifest: dict[str, Any], metrics: dict[str, Any]) -> str:
    return "\n".join([
        f"# Semantic Compute-Worthiness Results — {manifest['preparation_id']}", "",
        "> Private human-label-derived evidence. Do not commit this file.", "",
        f"Reviewed: {metrics['reviewed']}/{metrics['target']}",
        f"Status: **{metrics['status']}**", "",
        "```json", json.dumps(metrics, ensure_ascii=False, indent=2), "```", "",
    ])


def generate_worthiness_report(
    manifest: dict[str, Any], protocol: WorthinessProtocol,
    judgments_path: str | Path, replacements_path: str | Path,
    output_root: str | Path,
) -> tuple[dict[str, Any], Path, Path]:
    metrics = calculate_worthiness_metrics(
        manifest, load_jsonl(judgments_path), load_jsonl(replacements_path), protocol,
    )
    path = Path(output_root) / manifest["preparation_id"] / "report.md"
    path.write_text(render_private_report(manifest, metrics), encoding="utf-8")
    safe_metrics = {
        key: value for key, value in metrics.items()
        if key != "employer_blind_spots_private"
    }
    aggregate = {
        "schema_version": 1,
        "artifact_type": "REPOSITORY_SAFE_SEMANTIC_WORTHINESS_RESULT",
        "preparation_id": manifest["preparation_id"],
        "experiment_id": manifest["experiment_id"],
        "protocol_version": manifest["protocol_version"],
        "protocol_fingerprint": manifest["protocol_fingerprint"],
        "generated_at": utc_now(),
        "metrics": safe_metrics,
        "provenance": {
            "private_manifest_sha256": _sha256_file(
                Path(output_root) / manifest["preparation_id"] / "manifest.json"
            ),
            "private_report_sha256": _sha256_file(path),
            "private_judgments_sha256": (
                _sha256_file(judgments_path) if Path(judgments_path).exists() else None
            ),
            "private_replacements_sha256": (
                _sha256_file(replacements_path) if Path(replacements_path).exists() else None
            ),
        },
        "privacy": {
            "detailed_rows_and_human_notes": "PRIVATE_LOCAL",
            "aggregate_result": "REPOSITORY_SAFE",
        },
        "limitations": [
            "This bounded sample is exploratory and not a statistically definitive product validation.",
            "Passing directional gates is necessary but not sufficient for runtime triage promotion.",
            "Counterfactual economics use sample labels and current-population projections.",
        ],
    }
    aggregate_path = Path(output_root) / manifest["preparation_id"] / "aggregate_result.json"
    aggregate_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n")
    return metrics, path, aggregate_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and evaluate semantic compute-worthiness human validation",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--output-root")
    parser.add_argument("--judgments")
    parser.add_argument("--replacements")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--preparation-id")
    record = sub.add_parser("record")
    record.add_argument("preparation_id")
    record.add_argument("label", choices=sorted(PRIMARY_LABELS))
    identity = record.add_mutually_exclusive_group(required=True)
    identity.add_argument("--review-number", type=int)
    identity.add_argument("--cluster-id")
    record.add_argument("--reason", action="append", default=[])
    record.add_argument("--note")
    record.add_argument("--supersedes")
    replace = sub.add_parser("replace")
    replace.add_argument("preparation_id")
    replace.add_argument("--review-number", type=int, required=True)
    replace.add_argument("--reason", default="UNAVAILABLE")
    report = sub.add_parser("report")
    report.add_argument("preparation_id")
    args = parser.parse_args()

    protocol = load_worthiness_protocol(args.config)
    output_root = args.output_root or protocol.raw["outputs"]["root"]
    judgments = args.judgments or protocol.raw["outputs"]["judgments"]
    replacements = args.replacements or protocol.raw["outputs"]["replacements"]
    if args.command == "prepare":
        result = prepare_worthiness_validation(
            args.database, args.config, output_root, preparation_id=args.preparation_id,
        )
        print(json.dumps({
            "preparation_id": result["preparation_id"],
            "private_manifest_path": result["private_manifest_path"],
            "private_blind_review_path": result["private_blind_review_path"],
            "aggregate_summary_path": result["aggregate_summary_path"],
            "sample": result["aggregate"]["sample"],
            "external_semantic_calls": 0,
            "live_source_calls": 0,
        }, indent=2))
        return 0
    manifest = load_preparation(output_root, args.preparation_id)
    if args.command == "record":
        value = append_worthiness_judgment(
            manifest, judgments, replacements, args.label,
            review_number=args.review_number, cluster_id=args.cluster_id,
            reasons=args.reason, note=args.note, supersedes=args.supersedes,
        )
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    if args.command == "replace":
        value = append_replacement(
            manifest, replacements, judgments, args.review_number, args.reason,
        )
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    metrics, path, aggregate_path = generate_worthiness_report(
        manifest, protocol, judgments, replacements, output_root,
    )
    print(json.dumps({
        "private_report": str(path), "aggregate_result": str(aggregate_path),
        "status": metrics["status"],
        "reviewed": metrics["reviewed"], "target": metrics["target"],
        "gates": metrics["gates"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
