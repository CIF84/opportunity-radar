from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
import yaml
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from opportunity_radar.adapters.base import ConfirmedEmptyInventoryError, SchemaMismatchError, clean_text, locations_from_raw, parse_datetime, value_at_path, work_mode_from_explicit
from opportunity_radar.config import CompanyConfig, load_companies
from opportunity_radar.models import JobReference, ListingFacts, WorkMode
from opportunity_radar.registry import AdapterRegistry
from opportunity_radar.scope_selection import load_market_scope, select_for_detail
from opportunity_radar.source_portfolio_audit import classify_role_families, load_source_portfolio_audit_config


DEFAULT_CONFIG = Path("experiments/wave_a_source_preflight_v1.yaml")
EXPERIMENT_TYPE = "WAVE_A_ZERO_DETAIL_SOURCE_CONTRACT_PREFLIGHT"
VERDICTS = {
    "GO_CONFIGURATION_ONLY", "GO_BOUNDED_ADAPTER_FIX",
    "CONDITIONAL_SOURCE_INVESTIGATION", "NO_GO_LOW_MARGINAL_VALUE",
    "NO_GO_SOURCE_CONTRACT",
}


class WaveAPreflightError(ValueError):
    pass


class RequestBudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class WaveAPreflightConfig:
    raw: dict[str, Any]
    fingerprint: str

    @property
    def sources(self) -> list[dict[str, Any]]:
        return self.raw["sources"]


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_state() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip())
    return {"commit": commit, "dirty": dirty}


def load_wave_a_preflight_config(path: str | Path = DEFAULT_CONFIG) -> WaveAPreflightConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required = {
        "schema_version", "experiment_id", "experiment_type", "companies_path",
        "database_path", "market_scope_path", "role_audit_config_path", "safety",
        "role_extension", "sources", "privacy", "outputs",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise WaveAPreflightError("Wave A preflight config has an invalid schema")
    if raw["schema_version"] != 1 or raw["experiment_type"] != EXPERIMENT_TYPE:
        raise WaveAPreflightError("unsupported Wave A preflight identity")
    if not isinstance(raw["sources"], list) or len(raw["sources"]) != 9:
        raise WaveAPreflightError("Wave A preflight must contain exactly nine sources")
    ids = []
    for item in raw["sources"]:
        if not isinstance(item, dict) or set(item) != {
            "company_id", "company_name", "category", "diversification", "probe", "company",
        }:
            raise WaveAPreflightError("invalid Wave A source entry")
        ids.append(item["company_id"])
        company = CompanyConfig.from_dict({
            "company_id": item["company_id"], "company_name": item["company_name"], **item["company"],
        })
        if company.company_id != item["company_id"]:
            raise WaveAPreflightError("source/company identity mismatch")
        if item["probe"] not in {"adapter_list_jobs", "alma_discovery_list_jobs", "nested_json_feed"}:
            raise WaveAPreflightError("unsupported Wave A probe")
    if len(ids) != len(set(ids)):
        raise WaveAPreflightError("Wave A company IDs must be unique")
    safety = raw["safety"]
    if set(safety) != {"connect_timeout_seconds", "read_timeout_seconds", "max_requests_per_source", "max_inventory_per_source"}:
        raise WaveAPreflightError("invalid request safety policy")
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in safety.values()):
        raise WaveAPreflightError("request safety values must be positive integers")
    if raw["privacy"] != {"detailed_artifact": "PRIVATE_LOCAL", "aggregate_artifact": "REPOSITORY_SAFE"}:
        raise WaveAPreflightError("invalid Wave A privacy boundary")
    extension = raw["role_extension"]
    if not isinstance(extension, dict) or set(extension) != {"contract_version", "families"}:
        raise WaveAPreflightError("invalid title-only role extension")
    if not isinstance(extension["families"], dict):
        raise WaveAPreflightError("role extension families must be a mapping")
    for patterns in extension["families"].values():
        if not isinstance(patterns, list) or not patterns or any(not isinstance(pattern, str) for pattern in patterns):
            raise WaveAPreflightError("role extension patterns must be non-empty string lists")
        for pattern in patterns:
            re.compile(pattern, re.I)
    return WaveAPreflightConfig(raw, hashlib.sha256(_stable_json(raw).encode()).hexdigest())


class BoundedSession(requests.Session):
    """Count and constrain public index requests; reject known detail contracts."""

    def __init__(self, max_requests: int, connect_timeout: int, read_timeout: int):
        super().__init__()
        self.max_requests = max_requests
        self.timeout = (connect_timeout, read_timeout)
        self.request_log: list[dict[str, Any]] = []
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504, 520), allowed_methods=frozenset({"GET", "POST"}))
        self.mount("https://", HTTPAdapter(max_retries=retry))
        self.headers.setdefault("User-Agent", "OpportunityRadarWaveAPreflight/1.0 (+public listing index only)")

    @staticmethod
    def _is_detail_request(url: str, kwargs: dict[str, Any]) -> bool:
        payload = kwargs.get("json")
        if isinstance(payload, dict):
            query = str(payload.get("query", ""))
            if "$jobAdId" in query or re.search(r"\bjobAd\s*\(\s*id", query):
                return True
        path = urlsplit(url).path.casefold()
        return bool(re.search(r"/jobs/[^/]+$", path) and not path.endswith("/jobs"))

    def request(self, method: str, url: str, **kwargs: Any):
        if self._is_detail_request(url, kwargs):
            raise WaveAPreflightError(f"detail request blocked by zero-detail preflight: {urlsplit(url).path}")
        if len(self.request_log) >= self.max_requests:
            raise RequestBudgetExceeded(f"source request ceiling {self.max_requests} reached")
        kwargs.setdefault("timeout", self.timeout)
        entry = {
            "method": method.upper(),
            "url": f"{urlsplit(url).scheme}://{urlsplit(url).netloc}{urlsplit(url).path}",
            "status_code": None,
        }
        self.request_log.append(entry)
        try:
            response = super().request(method, url, **kwargs)
        except requests.RequestException as exc:
            entry["error_type"] = type(exc).__name__
            raise
        entry["url"] = f"{urlsplit(response.url).scheme}://{urlsplit(response.url).netloc}{urlsplit(response.url).path}"
        entry["status_code"] = response.status_code
        return response


def _company_config(item: dict[str, Any], options: dict[str, Any] | None = None) -> CompanyConfig:
    raw = {"company_id": item["company_id"], "company_name": item["company_name"], **item["company"]}
    if options is not None:
        raw["options"] = options
    return CompanyConfig.from_dict(raw)


def _alma_credentials(html: str, base_url: str, session: BoundedSession) -> tuple[str, str, str]:
    # Newer Alma pages expose exactly the browser widget configuration inline.
    match = re.search(r"__LMC_CAREER_WIDGET__\.push\((\{.*?\})\)\s*;", html, re.S)
    if match:
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError:
            value = None
        if isinstance(value, dict) and value.get("widgetId") and value.get("apiKey"):
            return str(value["widgetId"]), str(value["apiKey"]), str(value.get("detailPath") or "/detail")
    soup = BeautifulSoup(html, "html.parser")
    patterns = (
        re.compile(r'''["']id["']\s*:\s*["']([0-9a-f-]{36})["'][^}]*?["']apiKey["']\s*:\s*["']([0-9a-f]{64})["']([^}]*)''', re.I),
        re.compile(r'''widgetId["']?\s*:\s*["']([0-9a-f-]{36})["'][^}]*?apiKey["']?\s*:\s*["']([0-9a-f]{64})["']([^}]*)''', re.I),
    )
    texts = [html]
    for script in soup.select("script[src]")[:30]:
        texts.append(session.get(urljoin(base_url, str(script["src"]))).text)
    for text in texts:
        for pattern in patterns:
            found = pattern.search(text)
            if found:
                detail = re.search(r'''detailPath["']?\s*:\s*["']([^"']+)''', found.group(3), re.I)
                return found.group(1), found.group(2), detail.group(1) if detail else "/detail"
    raise SchemaMismatchError("Alma widget credentials not found in bounded public configuration")


def _nested_json_references(item: dict[str, Any], company: CompanyConfig, session: BoundedSession) -> tuple[list[JobReference], dict[str, Any]]:
    response = session.get(company.endpoint_url)
    response.raise_for_status()
    data = response.json()
    options = company.options
    groups = value_at_path(data, options.get("groups_path"))
    if not isinstance(groups, list):
        raise SchemaMismatchError("nested JSON group path is not a list")
    refs: list[JobReference] = []
    count_mismatches = []
    fields = options["fields"]
    for group in groups:
        jobs = value_at_path(group, options["items_path"])
        expected = value_at_path(group, options["group_count_path"])
        if not isinstance(jobs, list) or not isinstance(expected, int):
            raise SchemaMismatchError("nested JSON group jobs/count schema mismatch")
        if len(jobs) != expected:
            count_mismatches.append({"group": value_at_path(group, options["group_name_path"]), "expected": expected, "actual": len(jobs)})
        for job in jobs:
            external_id = value_at_path(job, fields["external_job_id"])
            title = value_at_path(job, fields["title"])
            url = value_at_path(job, fields["canonical_url"])
            if external_id is None or not title or not url:
                raise SchemaMismatchError("nested JSON job identity/title schema mismatch")
            values = value_at_path(job, fields["locations"], []) or []
            if isinstance(values, dict):
                values = list(values.values())
            if not values and fields.get("location"):
                values = [value_at_path(job, fields["location"])]
            raw_locations = []
            for value in values:
                if isinstance(value, dict):
                    value = value.get("name") or value.get("location") or ", ".join(str(x) for x in value.values() if x)
                if value:
                    raw_locations.append(str(value))
            mode = work_mode_from_explicit(raw_locations)
            refs.append(JobReference(
                company.company_id, str(external_id), str(url), {"item": job},
                ListingFacts(
                    title=clean_text(str(title)), locations=tuple(locations_from_raw(raw_locations)),
                    work_mode=mode if mode is not WorkMode.UNSPECIFIED else None,
                    department=clean_text(str(value_at_path(group, options["group_name_path"]) or "")),
                    source_updated_at=parse_datetime(value_at_path(job, fields["source_updated_at"])),
                ),
            ))
    if count_mismatches:
        raise SchemaMismatchError(f"nested JSON group count mismatch: {count_mismatches}")
    return refs, {"group_count": len(groups), "group_counts_validated": True}


def _database_counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        names = ["ingestion_runs", "source_observations", "job_instances", "job_observations", "events", "semantic_assessments"]
        return {name: int(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]) for name in names if name in tables}
    finally:
        connection.close()


def _listing_metrics(refs: list[JobReference], scope: Any, role_config: Any, role_extension: dict[str, Any] | None = None) -> dict[str, Any]:
    fields = Counter()
    market = Counter()
    roles = Counter()
    private_rows = []
    for ref in refs:
        facts = ref.listing_facts
        fields["title"] += bool(facts.title)
        fields["canonical_url"] += bool(ref.canonical_url)
        fields["location"] += bool(facts.locations)
        fields["work_mode"] += bool(facts.work_mode)
        fields["date"] += bool(facts.date_posted or facts.source_updated_at)
        fields["department"] += bool(facts.department)
        fields["employment_type"] += bool(facts.employment_type)
        selection = select_for_detail(facts, scope)
        market[selection.decision.value] += 1
        matches = classify_role_families(facts.title, None, role_config)
        for match in matches:
            roles[match.family] += 1
        for family, patterns in (role_extension or {}).get("families", {}).items():
            if facts.title and any(re.search(pattern, facts.title, re.I) for pattern in patterns):
                roles[family] += 1
        private_rows.append({
            "external_job_id": ref.external_job_id, "canonical_url": ref.canonical_url,
            "listing_facts": facts.to_dict(), "scope_decision": selection.decision.value,
            "scope_reason": selection.reason, "role_families": [match.payload() for match in matches],
        })
    present_ids = [ref.external_job_id for ref in refs if ref.external_job_id]
    unique_ids = len(set(present_ids))
    unique_urls = len({ref.canonical_url for ref in refs})
    selected = sum(value for key, value in market.items() if key != "SKIP_EXPLICITLY_OUT_OF_SCOPE")
    return {
        "listing_field_counts": dict(fields), "market_scope_counts": dict(market),
        "role_family_title_counts": dict(roles), "selected_for_detail": selected,
        "projected_network_detail_requests": selected, "unique_external_ids": unique_ids,
        "unique_canonical_urls": unique_urls,
        "duplicate_external_id_count": len(present_ids) - unique_ids,
        "duplicate_canonical_url_count": len(refs) - unique_urls,
        "private_rows": private_rows,
    }


def _verdict(result: dict[str, Any], adapter_gap: bool, target_families: set[str]) -> str:
    if result["status"] != "SUCCESS" or not result["inventory"]["complete"]:
        return "NO_GO_SOURCE_CONTRACT"
    count = result["inventory"]["count"]
    target = sum(result["target_role_family_counts"].get(key, 0) for key in target_families)
    if count == 0 or target == 0:
        return "NO_GO_LOW_MARGINAL_VALUE"
    if adapter_gap:
        return "GO_BOUNDED_ADAPTER_FIX"
    unknown = result["market_scope_counts"].get("SELECT_GEOGRAPHY_UNKNOWN", 0)
    if count and unknown / count >= 0.8:
        return "CONDITIONAL_SOURCE_INVESTIGATION"
    return "GO_CONFIGURATION_ONLY"


def run_wave_a_preflight(config_path: str | Path = DEFAULT_CONFIG, output_root: str | Path | None = None, run_id: str | None = None, write_artifact: bool = True) -> dict[str, Any]:
    config = load_wave_a_preflight_config(config_path)
    raw = config.raw
    companies_path, database_path = Path(raw["companies_path"]), Path(raw["database_path"])
    companies_sha_before, database_sha_before = _sha256(companies_path), _sha256(database_path)
    rows_before = _database_counts(database_path)
    production_ids = {company.company_id for company in load_companies(companies_path)}
    if production_ids & {item["company_id"] for item in config.sources}:
        raise WaveAPreflightError("Wave A preflight companies must not be production configured")
    scope = load_market_scope(raw["market_scope_path"])
    role_config = load_source_portfolio_audit_config(raw["role_audit_config_path"])
    target_families = set(role_config.raw["target_role_families"])
    safety = raw["safety"]
    results = []
    for index, item in enumerate(config.sources, 1):
        print(f"[{index}/9] START company={item['company_id']} probe={item['probe']}", flush=True)
        session = BoundedSession(safety["max_requests_per_source"], safety["connect_timeout_seconds"], safety["read_timeout_seconds"])
        started = datetime.now(timezone.utc)
        refs: list[JobReference] = []
        diagnostics: dict[str, Any] = {}
        adapter_gap = False
        status, error_type, error_message = "SUCCESS", None, None
        try:
            company = _company_config(item)
            if item["probe"] == "nested_json_feed":
                refs, diagnostics = _nested_json_references(item, company, session)
                adapter_gap = True
            else:
                if item["probe"] == "alma_discovery_list_jobs":
                    landing = session.get(company.endpoint_url)
                    landing.raise_for_status()
                    widget_id, api_key, detail_path = _alma_credentials(landing.text, company.endpoint_url, session)
                    options = {**company.options, "widget_id": widget_id, "api_key": api_key, "detail_path": detail_path}
                    company = _company_config(item, options)
                    adapter_gap = True
                    diagnostics = {"credential_discovery": "BOUNDED_PUBLIC_WIDGET_CONFIGURATION", "credentials_persisted": False}
                adapter = AdapterRegistry.create(company)
                adapter.session = session
                try:
                    refs = adapter.list_jobs(company)
                except ConfirmedEmptyInventoryError:
                    refs = []
                    diagnostics["confirmed_empty"] = True
                if company.adapter == "successfactors":
                    diagnostics["listing_geography_contract"] = "AVAILABLE" if any(ref.listing_facts.locations for ref in refs) else "NOT_EXPOSED"
            if len(refs) > safety["max_inventory_per_source"]:
                raise RequestBudgetExceeded("inventory safety ceiling exceeded")
            metrics = _listing_metrics(refs, scope, role_config, raw["role_extension"])
        except Exception as exc:  # isolate all nine public source probes
            status, error_type, error_message = "FAILED", type(exc).__name__, str(exc)[:1000]
            metrics = _listing_metrics([], scope, role_config, raw["role_extension"])
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        result = {
            "company_id": item["company_id"], "company_name": item["company_name"],
            "category": item["category"], "diversification": item["diversification"],
            "provider_adapter": item["company"]["adapter"], "source_url": item["company"]["endpoint_url"],
            "probe": item["probe"], "status": status,
            "inventory": {
                "count": len(refs), "complete": status == "SUCCESS",
                "termination_evidence": "SOURCE_CONTRACT_COMPLETED" if status == "SUCCESS" else "NOT_PROVEN",
                "unique_external_ids": metrics["unique_external_ids"],
                "unique_canonical_urls": metrics["unique_canonical_urls"],
                "duplicate_external_id_count": metrics["duplicate_external_id_count"],
                "duplicate_canonical_url_count": metrics["duplicate_canonical_url_count"],
            },
            "listing_field_counts": metrics["listing_field_counts"],
            "market_scope_counts": metrics["market_scope_counts"],
            "target_role_family_counts": {key: value for key, value in metrics["role_family_title_counts"].items() if key in target_families},
            "all_role_family_counts": metrics["role_family_title_counts"],
            "projected_detail_burden": {
                "selected_for_detail": metrics["selected_for_detail"],
                "projected_network_detail_requests": metrics["projected_network_detail_requests"],
                "zero_network_detail_advantage": 0,
            },
            "adapter_reuse_without_code_change": not adapter_gap,
            "bounded_adapter_gap": "NESTED_JSON_GROUP_FLATTENING" if item["probe"] == "nested_json_feed" else ("ALMA_INLINE_WIDGET_DISCOVERY" if adapter_gap else None),
            "diagnostics": diagnostics,
            "requests": {"count": len(session.request_log), "ceiling": session.max_requests, "log": session.request_log},
            "error_type": error_type, "error_message": error_message,
            "elapsed_seconds": round(elapsed, 3), "private_rows": metrics["private_rows"],
        }
        if metrics["duplicate_external_id_count"]:
            adapter_gap = True
            result["adapter_reuse_without_code_change"] = False
            result["bounded_adapter_gap"] = "NON_UNIQUE_EXTERNAL_ID_LISTING_MAPPING"
        risks = []
        if status != "SUCCESS":
            risks.append("INVENTORY_INCOMPLETE")
        if refs and not any(ref.listing_facts.locations for ref in refs):
            risks.append("LISTING_GEOGRAPHY_UNAVAILABLE")
        if metrics["duplicate_external_id_count"]:
            risks.append("NON_UNIQUE_EXTERNAL_JOB_ID")
        if result["bounded_adapter_gap"]:
            risks.append(result["bounded_adapter_gap"])
        result["operational_risks"] = risks
        result["verdict"] = _verdict(result, adapter_gap, target_families)
        if result["verdict"] not in VERDICTS:
            raise AssertionError("invalid verdict")
        results.append(result)
        print(f"[{index}/9] {status} company={item['company_id']} jobs={len(refs)} requests={len(session.request_log)} verdict={result['verdict']}", flush=True)

    companies_sha_after, database_sha_after = _sha256(companies_path), _sha256(database_path)
    rows_after = _database_counts(database_path)
    if companies_sha_before != companies_sha_after or database_sha_before != database_sha_after or rows_before != rows_after:
        raise WaveAPreflightError("read-only integrity invariant failed")
    run_id = run_id or f"wave-a-preflight-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    result = {
        "schema_version": 1, "experiment_id": raw["experiment_id"], "experiment_type": EXPERIMENT_TYPE,
        "run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(),
        "sources": results,
        "configuration": {"fingerprint": config.fingerprint, "git": _git_state()},
        "integrity": {
            "companies_sha256_before": companies_sha_before, "companies_sha256_after": companies_sha_after,
            "database_sha256_before": database_sha_before, "database_sha256_after": database_sha_after,
            "database_rows_before": rows_before, "database_rows_after": rows_after,
            "production_companies_unchanged": True, "database_byte_identical": True,
            "phase2_rows_unchanged": True, "semantic_calls": 0, "detail_calls": 0,
        },
    }
    if write_artifact:
        directory = Path(output_root or raw["outputs"]["root"]) / run_id
        directory.mkdir(parents=True, exist_ok=False)
        detail_path = directory / "preflight.json"
        detail_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        safe_sources = []
        for row in results:
            safe = {key: value for key, value in row.items() if key not in {"private_rows", "error_message"}}
            safe["requests"] = {"count": row["requests"]["count"], "ceiling": row["requests"]["ceiling"]}
            safe_sources.append(safe)
        first_wave = [
            row["company_id"] for row in safe_sources
            if row["verdict"] == "GO_CONFIGURATION_ONLY"
            and row["market_scope_counts"].get("SELECT_IN_SCOPE", 0) > 0
        ][:5]
        secondary = [
            row["company_id"] for row in safe_sources
            if row["company_id"] not in first_wave
            and row["verdict"] in {"GO_CONFIGURATION_ONLY", "GO_BOUNDED_ADAPTER_FIX", "CONDITIONAL_SOURCE_INVESTIGATION"}
        ]
        aggregate = {
            "schema_version": 1, "experiment_id": raw["experiment_id"], "experiment_type": EXPERIMENT_TYPE,
            "run_id": run_id, "created_at": result["created_at"], "sources": safe_sources,
            "first_onboarding_wave": first_wave,
            "secondary_candidates": secondary,
            "do_not_onboard_yet": [row["company_id"] for row in safe_sources if row["verdict"].startswith("NO_GO")],
            "configuration": result["configuration"], "integrity": result["integrity"],
            "privacy": {
                "detailed_artifact": "PRIVATE_LOCAL", "detailed_sha256": _sha256(detail_path),
                "repository_safe_aggregate": "aggregate_summary.json",
                "excluded_detail": "JOB_TITLES_URLS_IDENTITIES_AND_SOURCE_RESPONSE_EVIDENCE",
            },
            "limitations": [
                "Listing-title classification is a neutral zero-detail signal, not candidate suitability scoring.",
                "Current vacancy inventory and source contracts are volatile public evidence.",
                "Retrieval-scope estimates preserve unknown geography and are not final candidate eligibility.",
                "A GO verdict authorizes only a later bounded onboarding packet, not production onboarding.",
            ],
        }
        aggregate_path = directory / "aggregate_summary.json"
        aggregate_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["artifact_paths"] = {"private_detailed": str(detail_path), "repository_safe_aggregate": str(aggregate_path)}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded zero-detail Wave A source-contract preflight")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-root")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run_wave_a_preflight(args.config, args.output_root, args.run_id, not args.dry_run)
    print(json.dumps({
        "run_id": result["run_id"], "source_count": len(result["sources"]),
        "verdicts": dict(Counter(row["verdict"] for row in result["sources"])),
        "requests": sum(row["requests"]["count"] for row in result["sources"]),
        "semantic_calls": 0, "detail_calls": 0, "artifact_paths": result.get("artifact_paths"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
