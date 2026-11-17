---
description: Run a read-only codebase audit across the dimensions below
argument-hint: [dimension or scope, e.g. security, database, backend/src/modules/fulfillment/domain/services, frontend/src/features/orders]
---

Run a READ-ONLY audit of the codebase (`backend/` and/or `frontend/` as relevant to scope). Do not modify any source files. Do not commit anything.

## Scope

Arguments given: `$ARGUMENTS`

- If `$ARGUMENTS` names a dimension (see list below), audit only that dimension across the whole codebase.
- If `$ARGUMENTS` names a path (e.g. `backend/src/modules/fulfillment/domain/services`, `frontend/src/features/orders`), audit all applicable dimensions but restrict findings to that path.
- If `$ARGUMENTS` is empty, run a broad audit across all dimensions.

Dimensions:
- architecture / layering / feature separation
- code duplication / component duplication
- code rot
- typing hygiene (mypy strict, TypeScript hygiene)
- database + migrations
- Pinia + API layer
- performance
- security
- API surface / OpenAPI compatibility
- UX consistency
- accessibility
- i18n
- logging discipline
- tests
- dead code + dependencies
- industry standard
- complexity (cognitive complexity via complexipy)

## Before starting

Read existing audit output files in `.audit/audit-<date>` first. They track residual items and conventions already accepted from the prior audit.

## Method

1. Fan out parallel read-only Explore (or general-purpose) subagents, one per dimension in scope. Each subagent searches and reads only, with no edits.
2. Before reporting any finding, verify it: it must cite a concrete `file:line`, and you must re-check that file:line yourself (or have the subagent re-check) before it goes in the report. Do not report a finding you have not personally verified.
3. Cross-check candidate findings against any earlier audit report the user points to and drop duplicates.

### Complexity dimension

Measured, not searched: run `cd backend && poetry run complexipy src --output-format json --output <scratchpad>/complexipy.json --quiet --ignore-complexity` (complexipy has no TS support, so `frontend/` is out of scope for this dimension; note that and skip it). From the JSON report:
- Totals: function count, mean, distribution buckets (0-5, 6-10, 11-15, 16-25, 26-40, >40), count above 15 (default threshold) and above 25, max.
- Per layer (`adapters`, `application`, `domain`, `infrastructure`, `ports`): count above 15 and max. Ports and domain should be near zero; a high count in `application` means fat `execute` bodies.
- Top 25 functions and top 8 files by summed complexity, with `file::function` and the score.
- If a prior audit folder has `complexipy.json`, diff the two: functions that crossed 15 or 25, and functions that grew by 5 or more.
Report as findings: every function above 40 is medium, the group above 25 is one medium finding listing them, and growth since the last audit is its own finding. A plain 2% above 15 is normal for a codebase this size and is not a finding on its own. Copy the JSON into the audit folder as `complexipy.json` so the next audit can diff against it.

## Output

Write a report to `.audit/audit-<today's date>/` (create the folder; use `YYYY-MM-DD` for today). Structure:
- Findings ranked by severity (high/medium/low).
- Each finding in the established work-package style: **Findings** (what and why), **Files** (file:line references), **Approach** (how it would be fixed), **Risk**, **Effort**.

Then send the user a short summary: dimension(s) covered, count of findings by severity, and the report path. Do not include the full report inline unless the user asks.

Hard constraints: this is read-only. Do not edit, create, or delete any source file. Do not run `git add`/`git commit`. The only file you write is the audit report itself.

## Models

Minimize token usage. Don't assume anything.
