# pdm administration

The admin routes of the SolidWorks PDM integration and the exact behaviour of its admin surfaces: the "PDM files" list, Retry and Dismiss, the sync run log, audit entries and log lines, the Web API console, the reconciliation report and the catalogue preview. The concepts are in [PDM_INTEGRATION.md sections 7, 13 and 14](../PDM_INTEGRATION.md#7-observability-and-administration).

- [1 admin routes](#1-admin-routes)
- [2 the pdm files list](#2-the-pdm-files-list)
- [3 retry and dismiss](#3-retry-and-dismiss)
- [4 the sync run log](#4-the-sync-run-log)
- [5 audit entries and log lines](#5-audit-entries-and-log-lines)
- [6 the web api console](#6-the-web-api-console)
- [7 the reconciliation report](#7-the-reconciliation-report)
  - [7.1 running a report](#71-running-a-report)
  - [7.2 categories](#72-categories)
  - [7.3 findings and retention](#73-findings-and-retention)
- [8 the catalogue preview](#8-the-catalogue-preview)

## 1 admin routes

All routes below are under `/api/v1/web/admin/settings` and need `read:settings` for a `GET` and `write:settings` for anything that writes, except where the table says otherwise. The API-key routes are in [pdm-sync.md section 2](pdm-sync.md#2-the-trigger-path) and [pdm-ingest.md section 8.2](pdm-ingest.md#82-the-api-key-surface).

| Method and path | Purpose |
|---|---|
| `GET /pdm` | Current settings plus a snapshot-state count for the connected vault. |
| `PUT /pdm` | Update the settings ([pdm-settings.md](pdm-settings.md)). |
| `POST /pdm/test` | "Test connection" probes a connection before it is saved. |
| `GET /pdm/operations` | The Web API console's operation catalogue. |
| `POST /pdm/operations/{operation_id}/invoke` | Runs one catalogued operation through the console. |
| `GET /pdm/workflows` | Vault workflows and states for the released, obsolete and replaced pickers. |
| `GET /pdm/folders` | Browses vault folders for the watched-folder picker. |
| `GET /pdm/users` | Vault users with their linked or proposed Glados user for the "Match PDM Users" dialog; it needs `write:settings`, since the dialog is reached only from the writable settings tab. |
| `POST /pdm/users/link` | Saves the links confirmed in that dialog, where `user_id: null` unlinks. |
| `POST /pdm/poll` | "Synchronize with PDM" queues an immediate poll. |
| `GET /pdm/files` | The "PDM files" list, paged and filtered. |
| `POST /pdm/files/{id}/retry` | Resets one snapshot row to pending and requests a refresh. |
| `POST /pdm/files/{id}/dismiss` | Drops a parked conflict's payload and marks the row skipped. |
| `GET /pdm/sync-activity` | What the sync is doing now: `requested` (a synchronisation waits for the scheduler), the poll `run` in progress with its live progress, and the 10 newest run entries across every run. |
| `POST /pdm/vault-files/{file_id}/retry` | The Retry action addressed by vault file id, used by the reconciliation dialog's re-check. |
| `GET /pdm/runs` | The sync run log, paged, newest first. |
| `GET /pdm/runs/{run_id}/entries` | One run's entries, optionally filtered by `action`. |
| `POST /pdm/reconcile` | Queues a reconciliation report (`deep` query parameter, default false). |
| `GET /pdm/reconciliation` | The latest reconciliation report: its run plus per-category counts. |
| `GET /pdm/reconciliation/findings` | The latest report's findings, paged and filtered. |

## 2 the pdm files list

- The list shows one row per file the poller or a refresh has ever seen under a watched folder, filterable by `sync_state` and `kind`, including `document`.
- The list reads `pdm_file_snapshot_table` (`PdmFileSnapshot`, `IPdmFileSnapshotRepository`), the same table the poller diffs against.
- Each row's `item_kind` names the catalogue its `item_id` belongs to; for a `document` row it comes from the file's document link.
- A `conflict` row's `has_parked_payload` says whether a payload is left to retry, and an `error` row's `last_error` holds the failure.
- The list has no live refresh: `pdm_file_snapshot_table` has no change-tracking registration on the frontend's realtime side, so the dialog relies on its own sync button and polling, like the audit and log tabs.
- The "Synchronize with PDM" button shows a spinning icon while a synchronisation is requested or running and opens the activity dialog, which polls `GET /pdm/sync-activity` every two seconds while it is open.

## 3 retry and dismiss

- Retry (`RetryPdmFile`) resets a row to `pending` and publishes the same `PdmFileChangeRequested` event as the trigger route, with `source="retry"`.
- Glados then re-reads the file from PDM itself, and nothing about the retry trusts the request beyond which row to retry.
- Dismiss (`DismissPdmFile`) drops the row's `parked_payload` and marks it `skipped` without contacting PDM, for a conflict an admin resolved by hand or decided not to sync.
- A dismissed row stays as a record, but the end-of-run conflict retry no longer picks it up, since nothing is parked.

## 4 the sync run log

- `pdm_sync_run_table` and `pdm_sync_run_entry_table` (`PdmSyncRun`, `PdmSyncRunEntry`, `IPdmSyncRunRepository`) record one row per poll tick, single-file refresh or reconciliation report, with one child entry per file, or per folder for a walk error.
- The log is the history behind the `last_poll_at`, `last_poll_error` and `last_poll_summary` status line on the settings row.
- Runs are kept for 30 days (`SYNC_RUN_RETENTION` in `domain/entities/pdm_sync_run.py`), and every run prunes older ones as its last step. Age rather than a count, because every single-file refresh is a run of its own.
- A single-file refresh run also carries `change_reason`, `change_state` and `requested_by_name`, the caller's reason, the destination state of a state change and the requester's full name, all null on poll and reconciliation runs. The admin runs list does not show them yet; the vault add-in's file history does ([pdm-sync.md section 2.6](pdm-sync.md#26-the-file-history-route)).
- Each run carries its trigger (`scheduled`, `manual`, `initial`, `file_trigger`, `retry`, `reconciliation`), its counts and `folders_walked`, which is always 0 for a single-file refresh or a reconciliation report, since neither browses a folder.
- Each entry carries an `action` and a message; the ingest actions are `created`, `revised`, `updated`, `status`, `claimed`, `skipped`, `conflict`, `missing` and `error`, and write-back, documents and thumbnails add their own ([pdm-writeback.md section 6](pdm-writeback.md#6-sync-log), [pdm-documents.md section 7](pdm-documents.md#7-run-entries)).
- A reconciliation run has no entries; its findings are read through `GET /pdm/reconciliation/findings`.

## 5 audit entries and log lines

- A settings update, a manual poll request, a Retry, a Dismiss and a mutating console operation that returned a 2xx each write a line to the settings audit log (`admin_settings_audit`, `settings_domain = "pdm"`).
- A connection test, a non-mutating console call and the workflow and folder browse proxies write no audit line, since they are read-only.
- Ingest logs one `info` line for each made create, made revise and bought create (`"PDM ingest {vault}/{file}: {action} item #{id}."`), one `info` line per PDM renumber and one `warning` per conflict.
- In-place updates, claims and status flips log no line of their own.
- The poller logs a `warning` per folder that failed to browse and an `exception` per file whose processing raised.
- A single-file refresh logs the same shape under `"PDM refresh ..."`.
- The scheduler logs an `exception` ("PdmPollScheduler: tick failed.") only when a tick's own top-level handling fails, which `PollPdmVault` avoids by recording `last_poll_error` itself first.

## 6 the web api console

- `HttpxPdmGateway` (`src/modules/external_data/adapters/outbound/external/pdm/client.py`) is the one adapter that speaks HTTP to the vault: one persistent `httpx.AsyncClient` per connection, a typed method per Web API call the codebase uses, and a generic `invoke` used only by the console.
- `catalogue.py` next to it is a generated table of the vault's full Web API surface (113 operations across 17 resource groups, 28 flagged mutating).
- It is generated by `backend/scripts/pdm_catalogue/` from the hand-finalised `operations.json`, which is drafted from the SOLIDWORKS help pages when a new Web API version ships.
- The `pdm-catalogue` pre-commit hook fails when `catalogue.py` is stale, and the file is never hand-edited.
- The console offers 99 operations: `application/services/pdm_console_policy.py` withholds the 14 that reconfigure the vault or bypass the list (add-in hook DLL and URL configuration, the file server root, the generic `api/{uri}` writes, destroying files and folders, editing vault users), because Glados would run them with the service account's rights and an add-in hook runs code on every PDM client.
- `ListPdmOperations` and `InvokePdmOperation` (`src/modules/external_data/application/use_cases/admin_settings/`) call any offered operation through the same `PdmSessionService`.
- A mutating operation needs two switches. The deployment must allow mutating operations at all with `PDM__ALLOW_MUTATING_OPERATIONS=true` (default `false`, refused with 403 `PdmMutatingOperationsDisabledError`), and the caller must pass `allow_mutating` for that call (refused with 400 otherwise), which matches the settings page's "Allow critical endpoints" switch.
- The PDM settings read model carries the deployment switch as `mutating_operations_enabled`. While it is false the console shows the "Allow critical endpoints" switch disabled with a tooltip naming the variable.
- A mutating call that succeeds is written to the settings audit log, since PDM's own history does not always attribute the Web API user clearly.
- The console never logs a request or response body or the bearer token, only the operation id and the resulting HTTP status.
- `invoke` percent-encodes every path parameter value, so a value cannot add path segments, a query or a fragment; the generic `uri` parameter keeps its slashes but rejects `..` segments.
- The response preview is truncated client-side at 512 KiB before it is shown or logged; that is Glados' display limit and says nothing about any size cap the vault's IIS server applies.

## 7 the reconciliation report

### 7.1 running a report

- The report is a comparison pass on request that never ingests anything and never calls PDM in quick mode.
- It runs as its own sync run (trigger `reconciliation`) and writes its findings to `pdm_reconciliation_finding_table` instead of run entries.
- `POST /pdm/reconcile?deep=false`, the default, reads only the database: `pdm_file_snapshot_table`, the made and bought catalogues, `part_number_registry` and `pdm_document_link_table`.
- `POST /pdm/reconcile?deep=true` runs every quick check and then reads the datacard of every linked made or bought file once more to compare `Glados.Ids` with what Glados has, the only category that calls the vault.
- A request sets a flag (`reconcile_requested_deep` carries the mode) that the scheduler's next tick, within 60 seconds, picks up and clears before that tick's poll-interval check, the same way `POST /pdm/poll` works.
- Only one reconciliation or poll runs at a time across all Gunicorn workers, under the same advisory lock as the poll tick.

### 7.2 categories

| Category | What it means |
|---|---|
| `orphaned_cad_row` | A CAD-owned item with no linked PDM file id, or whose linked file has no snapshot, or whose snapshot is `missing`. |
| `stuck_file` | A snapshot in `pending`, `error`, `conflict` or `skipped` for longer than `stuck_after_days`; one row per distinct reason and kind, with `count` holding how many files. A deliberate skip (state not watched, document state not released, document extension not ingested for the item's kind, unreadable for the PDM user, dismissed by an admin; `application/services/pdm_skip_reasons.py`) is not stuck, and documents are left to `document_unmatched`. |
| `revision_lag` | A linked file's snapshot version and the item's `pdm_file_version` disagree, in either direction. |
| `duplicate_part_number` | Two snapshots share a part number, a registry entry is carried by no live item, or a CAD item is unknown to the registry or registered under the other kind. |
| `kind_mismatch` | A linked snapshot's resolved kind disagrees with the kind the item is stored under. |
| `document_missing` | A document link whose snapshot is missing or gone. |
| `document_unmatched` | A `documents` folder file `PdmDocumentSync` never matched to an item; one row per distinct reason, with `count` holding how many files. An export waiting in a state documents are not synced from is not reported. |
| `unclaimed_match` | A parked bought-file conflict whose identity now matches an unlinked bought item by the gtin or manufacturer and order-code rule ingest uses, so it would be claimed on the next successful ingest. |
| `writeback_drift` | Deep mode only: a linked file's `Glados.Ids` differs from what Glados has, or could not be read at all (severity `info`, the error as the message). |
| `status_mismatch` | A linked row's `status` differs from the status its snapshot's workflow state implies under the kind's released, obsolete and replaced lists; a state outside all three is never compared. |
| `replaced_without_successor` | A row with `status` `replaced` and no `successor_item_id`; PDM never sets one, so this is always an unfinished web action. |
| `successor_without_replaced` | A row with a `successor_item_id` whose `status` is not `replaced`, for example a row ingest reactivated without the successor being cleared some other way. |
| `part_number_drift` | A linked row's `part_number` differs from the one its snapshot carries. Ingest heals it on the file's next ingest ([pdm-ingest.md section 4](pdm-ingest.md#4-renumbering)), and a manual synchronisation or a re-check from the report applies it at once. A made-item family linked to one file is reported once, with `count` holding the number of revision rows. |

### 7.3 findings and retention

- Every finding carries a `severity` (`info`, `warning` or `error`) and an optional `kind` (`made`, `bought` or `document`).
- A finding about one file carries its `item_id`, `file_id`, `part_number` and `revision`.
- An aggregated finding (`stuck_file`, `document_unmatched` and a multi-file `duplicate_part_number` group) leaves those four blank and uses `count` instead.
- A reconciliation run is pruned after 30 days like every other run, and its findings cascade-delete with it.
- `GET /pdm/reconciliation` and `GET /pdm/reconciliation/findings` always read the latest run with trigger `reconciliation`, so a report never accumulates across runs; each one replaces the dialog's view of the last.

## 8 the catalogue preview

- `GET /api/v1/web/pdm/preview?kind=made|bought` (`ListPdmPreview`) is open to any authenticated user, the same read rule as the made and bought item lists.
- It is derived entirely from `pdm_file_snapshot_table`, cross-checked against the live catalogue; it is not an item status, never creates a row, and is unrelated to the admin "PDM files" list.
- Only candidate rows are read, selected in SQL: the requested kind, a part number, not `missing`, and either no item link or a vault version newer than the one last ingested.
- The live-item check for unlinked rows is one batch query over their part numbers.
- The `unlinked` bucket holds snapshots with no item link (`item_id` null) whose part number has no live item of the requested kind either (made: no revision row of the family; bought: `get_by_part_number`), whatever the reason (not yet released, skipped, parked in conflict).
- The `newer` bucket holds snapshots linked to an existing item whose vault version is ahead of the item's `pdm_file_version`, including an item that never synced a version.
- For a made item, the `newer` row is whichever revision the snapshot points at, not necessarily the family's newest.
- The response's `enabled` flag is false with both lists empty whenever the integration is off or has no cached vault id yet, never an error, so the frontend can hide the preview button.
- The panel and badge live in the made and bought catalogue views (`frontend/src/shared/pdm-preview/`), not in the admin settings.
