# reference

The detailed rule tier of the documentation. The guides one level up in `docs/` explain what a part of Glados is, how it fits together and how to do the common tasks, and stay short enough to read in one sitting. The files here hold everything a change has to get exactly right: complete checklists, invariants, edge cases, exact settings and the reasoning behind a single rule. Contributors open them when a guide links to them, and AI agents load them through `CLAUDE.md` and the skills in `.claude/skills/`.

## how the two tiers split the work

Every fact lives in exactly one place. A guide explains a concept and links to the reference file that states its rules; a reference file states the rules and links back to the guide instead of explaining the concept again. When a guide and a reference file would say the same thing, the guide keeps the one sentence a reader needs to understand the idea and the reference file keeps the rule.

Neither tier copies what the code already says. File inventories, column lists, enum values and function signatures go stale the day they are written, so a document names the module or the migration that holds them instead.

Rules that a tool can check belong in that tool (`lint-imports`, ruff, `scripts/check_plan_refs.py`, `npm run check:i18n`, a guard test). The document then names the check in one sentence rather than restating the rule in prose.

## format of a reference file

A reference file covers one topic and is named after it in lowercase kebab case. It opens with a heading, one paragraph that says what it covers and which guide explains the concept, and a table of contents. Sections are numbered (`## 1 ...`, `### 1.1 ...`) so code comments and skills can point at `docs/reference/<file>.md section N`. Lists and tables are welcome, but every list item is a full sentence and the style rules of [CONTRIBUTING.md section 9](../CONTRIBUTING.md) apply as everywhere else.

## files

| File | Covers | Guide |
| ---- | ------ | ----- |
| [module-boundaries.md](module-boundaries.md) | Backend layers and modules, where new code goes, wiring, import contracts, cross-module patterns, frontend layers and the feature wall. | [CONTRIBUTING.md](../CONTRIBUTING.md) section 1 |
| [recipes.md](recipes.md) | Full step lists to add an endpoint, a field, a domain error, a frontend feature module, an admin settings tab or a PDF report. | [CONTRIBUTING.md](../CONTRIBUTING.md) section 2 |
| [backend-conventions.md](backend-conventions.md) | Enums, use cases and permissions, PATs, maintenance mode, idempotent writes, DTOs and schemas, quantities, delivery tolerance, logging, stored files, and composed mail with its attachments and the export journal. | [CONTRIBUTING.md](../CONTRIBUTING.md) sections 3 to 3.3 |
| [persistence.md](persistence.md) | Models, sessions, column types, repositories and mappers, load options, paging, the unit of work, seeding, soft delete, events and the outbox. | [CONTRIBUTING.md](../CONTRIBUTING.md) sections 3.4 to 3.6 |
| [lifecycle.md](lifecycle.md) | The lifecycle reconciler protocol, lock order, user actions, edit versions, lost races, the drift check and the lifecycle tests. | [CONTRIBUTING.md](../CONTRIBUTING.md) section 3.7 |
| [frontend-conventions.md](frontend-conventions.md) | Frontend code style, styling, API calls and types, i18n and German copy, stores and live updates, OpenVue pitfalls. | [CONTRIBUTING.md](../CONTRIBUTING.md) sections 4 and 5 |
| [design-look.md](design-look.md) | Page skeleton, tabs, buttons, tables, cards, dialogs and forms, settings tabs, feedback, visual language and copy. | [CONTRIBUTING.md](../CONTRIBUTING.md) section 4.1 |
| [handbook-pages.md](handbook-pages.md) | Handbook files, the help button and drawer wiring, frontmatter and writing style. | [CONTRIBUTING.md](../CONTRIBUTING.md) section 6 |
| [testing.md](testing.md) | Backend and frontend test rules: fixtures, fakes, mocks, factories, selectors and coverage. | [CONTRIBUTING.md](../CONTRIBUTING.md) section 7 |
| [domain-rules.md](domain-rules.md) | The rule-like detail behind the glossary terms. | [CONTRIBUTING.md](../CONTRIBUTING.md) section 10 |
| [scheduling.md](scheduling.md) | The forward walk, kept windows, passes, Auto-Plan, the tenant timezone, machine calendars and capability. | [CONTRIBUTING.md](../CONTRIBUTING.md) section 11 |
| [development-environment.md](development-environment.md) | Toolchain pins, the git hooks, how settings and env files are read, the staging clone script. | [DEVELOPMENT.md](../DEVELOPMENT.md) sections 1 to 4 |
| [development-migrations.md](development-migrations.md) | The single-head chain, immutable released migrations, and writing and checking a migration. | [DEVELOPMENT.md](../DEVELOPMENT.md) section 6 |
| [development-datetime.md](development-datetime.md) | UTC storage, the clock, tenant timezone accessors and day assignment. | [DEVELOPMENT.md](../DEVELOPMENT.md) section 8 |
| [development-testing.md](development-testing.md) | Running and isolating the backend suite, shared fixtures and fakes, property tests and Postgres race tests. | [DEVELOPMENT.md](../DEVELOPMENT.md) section 9 |
| [development-async.md](development-async.md) | What is async, offloading blocking work, the session rule and scheduled interval tasks. | [DEVELOPMENT.md](../DEVELOPMENT.md) section 10 |
| [releasing-ci.md](releasing-ci.md) | CI triggers, jobs and channel images, the `pat` snapshot check, the release workflow and the version scripts. | [RELEASING.md](../RELEASING.md) sections 2 and 5 |
| [releasing-github-setup.md](releasing-github-setup.md) | Repository settings, rulesets, code security and GHCR packages. | [RELEASING.md](../RELEASING.md) section 6 |
| [field-ownership.md](field-ownership.md) | The ownership principles in full, the per-field tables, claiming, lifecycle mapping, conflicts, enforcement and label properties. | [FIELD_OWNERSHIP.md](../FIELD_OWNERSHIP.md) |
| [pdm-settings.md](pdm-settings.md) | Every PDM setting, its validation and what a save requeues. | [PDM_INTEGRATION.md](../PDM_INTEGRATION.md) section 3 |
| [pdm-sync.md](pdm-sync.md) | The Web API session, the trigger routes and the periodic sync. | [PDM_INTEGRATION.md](../PDM_INTEGRATION.md) section 4 |
| [pdm-ingest.md](pdm-ingest.md) | The numbered ingest rules, the single transaction, renumbering, releaser attribution, required fields and pre-release validation. | [PDM_INTEGRATION.md](../PDM_INTEGRATION.md) section 5 |
| [pdm-admin.md](pdm-admin.md) | Admin routes, the PDM files list, the sync run log, the Web API console, the reconciliation report and the catalogue preview. | [PDM_INTEGRATION.md](../PDM_INTEGRATION.md) sections 7, 13 and 14 |
| [pdm-writeback.md](pdm-writeback.md) | What write-back writes, its gate, timing, error handling and sync log. | [PDM_INTEGRATION.md](../PDM_INTEGRATION.md) section 10 |
| [pdm-documents.md](pdm-documents.md) | The file type rule, `documents` folders, categories and storage, replacement and thumbnails. | [PDM_INTEGRATION.md](../PDM_INTEGRATION.md) section 11 |
| [terminal-auth.md](terminal-auth.md) | Device sign-in, terminal keys, approval, terminal actions, audit and per-route permissions. | [TERMINAL_INTEGRATION.md](../TERMINAL_INTEGRATION.md) sections 4 to 6 |
| [terminal-display.md](terminal-display.md) | Device state, the infoscreen page, device details, display power and messages. | [TERMINAL_INTEGRATION.md](../TERMINAL_INTEGRATION.md) sections 4.4 and 6 |
| [terminal-infoscreens.md](terminal-infoscreens.md) | Screen settings and layouts, widgets, feed contents, the no-persons rule and the live filter. | [TERMINAL_INTEGRATION.md](../TERMINAL_INTEGRATION.md) sections 7 and 8 |
| [terminal-security.md](terminal-security.md) | The full threat and mitigation table and residual risks for terminals. | [TERMINAL_INTEGRATION.md](../TERMINAL_INTEGRATION.md) section 10 |
| [time-tracking-provider.md](time-tracking-provider.md) | The contract with the time tracking service, sealed credentials, the binding, values and error codes, and the rules behind the Time Tracking view. | [TIME_TRACKING.md](../TIME_TRACKING.md) sections 2 and 5 |
| [time-tracking-credentials.md](time-tracking-credentials.md) | Time tracking settings, admin routes, the credential key, per-user credentials, encryption, fingerprint and lockout. | [TIME_TRACKING.md](../TIME_TRACKING.md) sections 3 and 4 |
| [time-tracking-security.md](time-tracking-security.md) | The mitigation table, secret handling, the consent dialog and residual risks for time tracking. | [TIME_TRACKING.md](../TIME_TRACKING.md) section 6 |
| [mcp-security.md](mcp-security.md) | How agents authenticate on the MCP surface, the gate permission, agent token lifetime, call budgets, result redaction, the agent call log, the agent settings and the threat model. | [MCP_INTEGRATION.md](../MCP_INTEGRATION.md) |
| [mcp-tools.md](mcp-tools.md) | Where agent tools live, how to write a read or draft tool, prompts and resources, the tool contract and testing a tool. | [MCP_INTEGRATION.md](../MCP_INTEGRATION.md) |
| [stock-service.md](stock-service.md) | The stock service settings, admin routes and the contract with the stock service. | [STOCK_SERVICE.md](../STOCK_SERVICE.md) |
| [eplan-data-portal.md](eplan-data-portal.md) | Portal calls, the field mapping, every entry point, ownership of the linked fields, pictures and the import settings. | [EPLAN_DATA_PORTAL_INTEGRATION.md](../EPLAN_DATA_PORTAL_INTEGRATION.md) |
| [operations-storage-and-backup.md](operations-storage-and-backup.md) | Storage provider internals, provider migration, the backup scheduler, the restore mechanics and the recovery strategy with the VM snapshots. | [OPERATIONS.md](../OPERATIONS.md) sections 2 to 4 |
| [operations-recovery.md](operations-recovery.md) | Recovery command internals, the system account, 2FA and lockout details, security setting defaults, dead letters, the RFID lookup, and the database restore. | [OPERATIONS.md](../OPERATIONS.md) section 5 |
| [operations-lifecycle-repair.md](operations-lifecycle-repair.md) | The drift report and repair commands in full, and how to settle the fact anomalies they list. | [OPERATIONS.md](../OPERATIONS.md) sections 5.9 and 5.10 |
| [operations-monitoring.md](operations-monitoring.md) | Log writing and fields, health and readiness, the full metric list, Prometheus multiprocess mode, worker shutdown and connection limits. | [OPERATIONS.md](../OPERATIONS.md) section 7 |
| [installation-deployment.md](installation-deployment.md) | Container nginx routing, why the proxy settings are required, HTTPS-dependent behaviour, forwarded addresses, Cloudflare Tunnel and bare metal. | [INSTALLATION.md](../INSTALLATION.md) |
