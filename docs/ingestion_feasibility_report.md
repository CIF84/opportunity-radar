# Opportunity Radar — Technical Ingestion Feasibility Report

Run date: 2026-08-20  
Scope: technical ingestion spike only  
Recommendation: **CONDITIONAL GO**

## Executive result

The spike did not meet the specification's full pass threshold, but it validated three reusable adapter families and the core architecture.

- 15 representative employers tested.
- 11 employers successfully ingested (73.3%); the target was at least 80%.
- Workday, Greenhouse, and SuccessFactors worked for three employers each without employer-specific Python branches.
- Generic first-party HTML worked for two of three employers.
- Alma Career / Jobs.cz did not work through static extraction: all three portals returned valid client-rendered shells but no vacancy records.
- 22 job details were sampled after complete inventory discovery (two details per successful employer).
- Required identity/completeness sample: company 100%, title 100%, location 100%, canonical URL 100%, external ID 100%, description 100%.
- Posting date completeness was 63.6%; missing dates were preserved as null.
- One vacancy remained one record when a source returned multiple locations.
- Employer failures were isolated and did not stop the run.

This is a conditional rather than unconditional GO because fewer than four families proved reliable, employer success was below 80%, and the currently proven families cover only 20 of the 50 research employers (40%) by family classification. The upper bound rises to 28/50 (56%) if the partially validated generic family is assumed to generalize, but the Allegro result shows that assumption is not yet justified.

## Live results

| Family | Employers | Successful | Result |
|---|---:|---:|---|
| Workday | 3 | 3 | Reusable |
| Greenhouse | 3 | 3 | Reusable |
| SuccessFactors | 3 | 3 | Reusable |
| Generic HTML | 3 | 2 | Partial |
| Alma Career | 3 | 0 | Not yet validated |
| **Total** | **15** | **11** | **73.3%** |

Successful employers were Johnson & Johnson, Red Hat, Pfizer, Pure Storage, Wrike, WPP, SAP, EY, Deutsche Börse Group, GoodData, and Kiwi.com.

The explicitly unsuccessful sources were:

- Siemens, Honeywell, and ČSOB: reachable Alma pages contained a JavaScript vacancy mount point but no vacancies in the returned HTML. These are recorded as `EMPTY`, not success.
- Allegro: the first-party archive was reachable, but job inventory was client-rendered and absent from returned HTML. This is also `EMPTY`.

## Adapter observations

### Workday

The same CXS API implementation handled all three tenants. It supports paginated inventory discovery, stable requisition IDs, separate detail retrieval, descriptions, dates, and multiple locations.

### Greenhouse

The public Job Board API implementation handled Pure Storage, Wrike, and WPP. The runtime sample uses Wrike because Productboard's researched Greenhouse board now returns HTTP 404.

### SuccessFactors

One declarative table/detail implementation handled SAP, EY, and Deutsche Börse Group. Pagination is configuration-driven. The same selectors retrieve inventories and descriptions without employer branches.

### Generic first-party HTML

The same selector and JSON-LD implementation handled GoodData and Kiwi.com. Exact selectors, detail selectors, pagination, and optional external-ID patterns live in configuration. Allegro demonstrated the boundary: a client-rendered source needs a documented feed/browser-capable extraction method, not a hidden company branch.

### Alma Career / Jobs.cz

The three branded portals share a JavaScript widget backed by a public platform client, rather than server-rendering vacancies. Static selector extraction cannot validate this family. A follow-up should implement and fixture the shared Alma widget API contract, or classify a browser/network-capture adapter as a separate reusable method. Zero results must continue to fail until the returned inventory can be positively validated.

## Corrections to research assumptions

The fingerprinted CSV was not modified. These corrections are recorded separately:

1. **Productboard:** `ats_family=greenhouse`, tenant `productboard`, and the researched Greenhouse board are stale. The public Greenhouse API returns HTTP 404; current vacancies are on Productboard's first-party careers pages. Wrike was substituted as the third Greenhouse reuse test.
2. **Siemens, Honeywell, ČSOB:** Alma classification remains correct, but `requires_javascript=unknown` should be treated as **yes for the observed listing path**, and plain HTML extraction is not sufficient.
3. **Allegro:** `requires_javascript=unknown` should be treated as **yes for the observed offer inventory**. The initial generic static-HTML assumption is incomplete.

No correction was silently applied to `research/target_companies.csv`; runtime configuration reflects only the live test set.

## Coverage analysis

Research family counts relevant to this spike are Workday 9, Greenhouse 5, SuccessFactors 6, Alma Career 9, and custom first-party 8.

- Fully validated reusable families: 9 + 5 + 6 = **20/50 (40%)**.
- Adding the partially validated custom/generic category as an optimistic upper bound: **28/50 (56%)**.
- Alma would add 9 employers if its shared widget contract is validated, taking these five families to an optimistic **37/50 (74%)** before other known standardized families are implemented.
- The research dataset identifies 6/50 employers (12%) as requiring bespoke code, within the README's 15% ceiling, but the spike did not independently validate all six classifications.

The current evidence therefore does not yet establish the README targets of 70% reusable ATS coverage or 85% with generic extraction.

## Recommendation

**CONDITIONAL GO** for one narrowly scoped follow-up ingestion iteration; **not a GO for the full Opportunity Radar product**.

Conditions:

1. Implement the shared Alma widget/API contract and demonstrate it across Siemens, Honeywell, and ČSOB using fixtures and live tests.
2. Add a reusable client-rendered/feed discovery method and retest Allegro plus at least two similar first-party sources.
3. Replace Productboard's stale research classification and endpoint in a deliberate research-data update.
4. Re-run the 15-employer acceptance set and require at least 12 successful employers and four reliable families before proceeding.
5. Expand adapters only to the already-researched standardized families (for example Ashby and SmartRecruiters) before considering product features.

UI, persistence, scoring, LLMs, notifications, and probabilistic deduplication remain out of scope.

## Reproduction

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest -q
.venv/bin/pytest -m live -o addopts='' -q
.venv/bin/opportunity-radar --max-jobs 2
```

Machine-readable evidence is in `output/jobs.json`, `output/run_results.json`, and `output/summary.json`.
