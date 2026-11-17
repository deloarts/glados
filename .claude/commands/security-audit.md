---
description: Run a read-only security audit of the codebase
argument-hint: [scope, e.g. backend | frontend | dependencies | a path]
---

Run a READ-ONLY security audit of the codebase (`backend/` and/or `frontend/` as relevant to scope). Do not modify any source files. Do not commit anything. Use local tools only; never send source code, diffs, or file contents to any external service.

This audits the whole codebase. To review only the pending changes on the current branch, use the built-in `/security-review` skill instead; it is the lighter tool for that job.

## Scope

Arguments given: `$ARGUMENTS`

- If `$ARGUMENTS` is empty, run a full audit across both halves: `backend/` and `frontend/`.
- If `$ARGUMENTS` is `backend` or `frontend`, audit only that half.
- If `$ARGUMENTS` is `dependencies`, audit dependency advisories only (skip the other dimensions).
- Otherwise treat `$ARGUMENTS` as a path (e.g. `backend/src/modules/fulfillment/adapters/inbound/api/v1/web`, `frontend/src/features/orders`): audit all applicable dimensions but restrict findings to that path.

## Dimensions

- **Authorization (backend)**: every non-public endpoint must resolve an actor via `auth_deps.py` and assert permissions via the domain permission-rule services (`src/modules/platform/domain/services/crud_permission_rules.py`) before the use case acts. Hunt for endpoints or use cases missing either check. Check PAT scoping (must be a subset of the issuing user's own permissions, never `write:settings` or other settings-adjacent scopes) and API-key auth paths. Check that maintenance-mode enforcement (503 + `MaintenanceModeError`, system/`write:settings`/allowlisted-IP exempt) cannot be bypassed on newly added routes.
- **Injection**: raw SQL / `text()` usage, string-built ILIKE patterns (global search), unsafe filter/sort parameter interpolation into queries, LDAP filter injection in the LDAP auth adapter, command execution, path traversal in file/storage/upload endpoints.
- **SSRF**: the webhook dispatcher (`httpx`) posts to admin-configured URLs, so check target validation and timeouts. Same for IPP/printer host handling and mail relay settings.
- **XSS + frontend sinks**: `v-html`, `innerHTML`, DOMPurify usage and gaps, user-controlled content rendered into templates, mail templates, or markdown/handbook rendering, URL handling and open redirects.
- **Secrets + sensitive data**: hardcoded credentials/tokens, secrets reaching logs or error messages (`src/modules/platform/adapters/inbound/api/exception_handlers.py` turns `DomainError` messages into client-visible `detail` strings, so flag any that embed secrets or internal paths), sensitive data written to `localStorage`, anything secret exposed through `VITE_`-prefixed env vars (baked into the client bundle at build time), settings endpoints leaking SMTP/LDAP credentials in responses, and no secrets or weak defaults baked into migrations or `init_db.py` seeding beyond `INIT__*` env-driven values.
- **AuthN/session**: token storage and transmission, 401/expiry handling, login error uniformity (user enumeration risk), rate limiting (e.g. `send:mail`), shared-account data isolation on logout (store/localStorage reset via `storeResetPlugin`).
- **Transport/headers/infra**: `docker/nginx.conf` (X-Forwarded-Proto handling), CORS config, cookie/header flags, CSP posture.
- **Dependencies**: in the backend, check what's actually available (`poetry run pip-audit` or similar) and report plainly if no such tool is installed rather than guessing at results; `npm audit` in the frontend.
- **Info leakage via SSE/live events**: whether events published to the `/live` SSE topic are filtered per user/permission before delivery, or broadcast to all connected users regardless of what they're allowed to see.

## Before starting

Read existing audit output files in `.audit/security-audit-<date>` first. They track residual items and conventions already accepted from the prior audit.

## Method

1. Fan out parallel read-only Explore (or general-purpose) subagents, one per dimension in scope. Each subagent searches and reads only, with no edits.
2. Before reporting any finding, verify it: it must cite a concrete `file:line`, and you must re-check that file:line yourself (or have the subagent re-check) before it goes in the report. Do not report a finding you have not personally verified.
3. Cross-check candidate findings against any earlier audit report the user points to and drop duplicates.

## Output

Write a report to `.audit/security-audit-<today's date>/` (create the folder; use `YYYY-MM-DD` for today). Structure:
- Findings ranked by severity (critical/high/medium/low).
- Each finding: **Finding** (what, and a concrete attack scenario: who can do what they shouldn't), **Files** (file:line references), **Approach** (how it would be fixed), **Risk**, **Effort**.
- Describe attack scenarios in prose. Do not write working exploit payloads into the report.

Then send the user a short summary: count of findings by severity and the report path. Do not include the full report inline unless the user asks.

Hard constraints: this is read-only. Do not edit, create, or delete any source file. Do not run `git add`/`git commit`. Use only local tools; never transmit code to an external service. The only files you write are the audit report files.

## Models

Use model `haiku` to investigate the codebase. Minimize token usage. Don't assume anything.
