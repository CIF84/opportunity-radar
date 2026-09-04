# Opportunity Radar — Technical Ingestion Feasibility Report

> Historical gate report. It remains evidence for the Phase 1 decision; use
> `docs/STATUS.md` for current project state and next work.

Run date: 2026-08-20  
Scope: ingestion feasibility only
Recommendation: **GO for the ingestion architecture; not authorization to build the product**

## Executive result

The follow-up validates the missing client-rendered families without browser automation or employer-specific Python branches.

- Original 15-employer acceptance set: **14/15 (93.3%)** in the current rerun. Johnson & Johnson exceeded the isolated live-run request window; its failure did not affect other employers. It had passed the prior spike.
- Expanded set including Schneider Electric, Roche, and Cisco: **17/18 (94.4%)**.
- Alma Career: Siemens, Honeywell, and ČSOB all pass listing pagination and detail retrieval through the same GraphQL implementation.
- JSON feed: Allegro and Schneider Electric pass through the same declarative implementation.
- Phenom: Roche and Cisco pass through the same `/widgets` `refineSearch` implementation.
- The 34-job detail sample has 100% completeness for company, title, location, canonical URL, external ID, and description; posting date completeness is 64.7%.
- No live empty inventory, schema mismatch, count mismatch, or request failure is converted into success.

Machine-readable evidence is in `output/jobs.json`, `output/run_results.json`, and `output/summary.json`.

## Adapter results

| Family | Employers in expanded run | Successful | Result |
|---|---:|---:|---|
| Workday | 3 | 2 | Reusable; one isolated live timeout |
| Greenhouse | 3 | 3 | Reusable |
| SuccessFactors | 3 | 3 | Reusable |
| Generic HTML | 2 | 2 | Reusable within declarative selector/JSON-LD boundary |
| Alma Career | 3 | 3 | Reusable |
| JSON feed | 2 | 2 | Reusable |
| Phenom | 2 | 2 | Reusable |
| **Total** | **18** | **17** | **94.4%** |

The original acceptance employers other than Johnson & Johnson all passed. The three added reuse tests—Schneider Electric, Roche, and Cisco—also passed.

## Follow-up implementations

### Alma Career

The adapter discovers the public widget name from the vacancy mount, reads the widget UUID, API key, and detail path from the portal's versioned configuration bundle, and calls the shared Capybara GraphQL endpoint. Listing traversal honors `lastPage` and validates the extracted identity count against `totalNumberOfItems`. Detail retrieval uses the shared `widget.jobAd` query. Siemens (62), Honeywell (13), and ČSOB (111) returned complete inventories through one code path.

### Declarative JSON feed

The adapter supports configured method, endpoint, query parameters, optional static body, item path, count/page paths, page parameter, and field mappings. It contains no company detection. Allegro's WordPress feed (177 jobs) and Schneider's Jibe feed (2,260 jobs during the recorded run) use the same implementation. Explicit source totals are enforced.

### Phenom

The dedicated adapter implements the common POST `/widgets` `refineSearch` payload and offset pagination. Roche (1,203 jobs) and Cisco (1,195 jobs) passed using only declarative endpoint and canonical-URL templates. Keeping this separate retains the platform contract instead of disguising it as arbitrary JSON mapping.

Browser automation is not necessary for any of these sources.

## Failure semantics and tests

Offline tests use deterministic response fixtures for credential discovery, listing/detail normalization, multiple employers per implementation, explicit zero inventory, and count mismatch. Live tests remain separately marked `live`. Listing failures are employer-scoped; detail failures are job-scoped. The following states remain distinct in output:

- `EMPTY`: a validated source count is zero, or extraction finds no records without proof of a non-empty inventory.
- `SchemaMismatchError`: required response structure or mapped fields changed.
- `CountMismatchError`: pagination output disagrees with the source's explicit total.
- `SourceRequestError`: HTTP request failure or timeout.

## Deliberate research corrections

The fingerprinted CSV has been updated rather than silently overridden. Its notes preserve the superseded assumption and validated finding:

1. Productboard's former Greenhouse tenant is stale; the current inventory is first-party HTML.
2. Siemens, Honeywell, and ČSOB use the shared Alma/Capybara GraphQL widget and require JavaScript in the presentation layer.
3. Allegro exposes a paginated WordPress JSON endpoint and is classified as `json_feed`.
4. Schneider Electric exposes a Jibe JSON feed and is classified as `jibe`.
5. Roche and Cisco share Phenom `/widgets` and are classified as `phenom`.
6. AstraZeneca's assets identify TalentBrew, not Phenom; TalentBrew remains unvalidated here.
7. Resistant AI currently exposes LinkedIn-only vacancy links and is downgraded to unsupported because LinkedIn scraping is out of scope.

## Coverage and bespoke-code analysis

After corrections, the 50-company dataset contains Alma 9, Workday 9, SuccessFactors 6, custom first-party 5, Greenhouse 4, Phenom 2, JSON feed 1, and Jibe 1 among the now-demonstrated categories.

- Families passing with at least two employers in the current expanded run cover **28/50 (56%)**. This conservative calculation excludes Workday because the current run was 2/3 after the Johnson & Johnson timeout.
- Including Workday, already demonstrated 3/3 in the original spike and still 2/3 in this rerun, validated reusable-family reach is **37/50 (74%)**.
- Research rows marked as requiring bespoke code: **7/50 (14%)**, within the 15% target.
- The client-rendered follow-up itself required **0/7 employer-specific Python branches (0%)**.

The 74% figure is dataset classification coverage, not a promise that every future tenant is schema-identical. Live tests and explicit mismatch states remain necessary.

## Recommendation

**GO** for the reusable ingestion architecture and another ingestion-only hardening iteration. The acceptance threshold is met, browser automation was unnecessary, and the new families demonstrate reuse across multiple employers.

This is not a GO to build Opportunity Radar product features. UI, persistence, scoring, LLMs, notifications, LinkedIn scraping, and probabilistic deduplication remain out of scope.

## Reproduction

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest -q
.venv/bin/pytest -m live -o addopts='' -q
.venv/bin/opportunity-radar --max-jobs 2
```
