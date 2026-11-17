# pdm sync

The exact behaviour of the two paths that discover a change in the PDM vault, the trigger path and the periodic sync, and of the Web API session both use. The concept is in [PDM_INTEGRATION.md section 4](../PDM_INTEGRATION.md#4-the-two-sync-paths); what ingest does with a file once one of these paths hands it over is in [pdm-ingest.md](pdm-ingest.md).

- [1 the web api session](#1-the-web-api-session)
- [2 the trigger path](#2-the-trigger-path)
  - [2.1 the changed-file route](#21-the-changed-file-route)
  - [2.2 the batch route](#22-the-batch-route)
  - [2.3 the trigger config route](#23-the-trigger-config-route)
  - [2.4 the rate limit](#24-the-rate-limit)
  - [2.5 the pdm sync worker](#25-the-pdm-sync-worker)
  - [2.6 the file history route](#26-the-file-history-route)
- [3 the periodic sync](#3-the-periodic-sync)
  - [3.1 scheduling and run triggers](#31-scheduling-and-run-triggers)
  - [3.2 the folder walk](#32-the-folder-walk)
  - [3.3 the diff](#33-the-diff)
  - [3.4 parallel ingest](#34-parallel-ingest)
  - [3.5 manual, scheduled and initial runs](#35-manual-scheduled-and-initial-runs)
  - [3.6 missing files and reappearance](#36-missing-files-and-reappearance)
  - [3.7 moves and renames](#37-moves-and-renames)
  - [3.8 kind conflicts and skips](#38-kind-conflicts-and-skips)
  - [3.9 conflict retries](#39-conflict-retries)
  - [3.10 cold-folder cadence](#310-cold-folder-cadence)
  - [3.11 run entries, progress and finish](#311-run-entries-progress-and-finish)
  - [3.12 database cost](#312-database-cost)

## 1 the web api session

- PDM's `authenticate()` opens a server-side session with no expiry claim and no logout, and each call is likely a license seat, so the bearer token is cached on the settings row itself (`session_token`, `session_user_id`, `session_obtained_at`) rather than in Redis or in a worker's memory.
- The cached token is shared by every Gunicorn worker and the background scheduler.
- `PdmSessionService` (`src/modules/external_data/application/services/pdm_session.py`) is the single seam every use case calls through.
- It reuses the stored token unless the token is missing or older than 24 hours, and authenticates only when it must.
- On a 401 from the gateway (`PdmSessionExpiredError`) it authenticates again and retries the call exactly once before giving up.
- A 503 with an empty body on a reused token gets the same treatment, because that is how the Web API reports a session it dropped on its own side; an idle timeout of roughly two hours was observed once the cold-folder cadence left the vault unpolled for that long.
- A missing token gets a 401 from the same endpoints, so only a reused token's 503 is read as a dropped session, and a 503 on a token obtained in the same call is a real outage that propagates.
- An authentication failure clears the stored session, so a rejected token is never reused on the next call.

## 2 the trigger path

### 2.1 the changed-file route

- `POST /api/v1/key/pdm/files/changed` (`src/modules/external_data/adapters/inbound/api/v1/key/endpoints/pdm.py`) is API-key only and gated by `use:pdm_addin`, so a key built for it can do nothing else.
- The body carries `vault_name`, which must match the configured vault, either `file_id` or `path` (at least one is required), and an optional `version` hint.
- The `version` hint is never trusted and is informational only: the consumer drops it, and neither the rate limit, the event worker's idempotency nor the snapshot uniqueness is keyed on it, so a trigger without a version, as the vault add-in sends after a rename, is processed like any other.
- The real version, state and variables are always re-read from the Web API downstream.
- `RequestPdmFileRefresh` (`src/modules/external_data/application/use_cases/pdm/request_pdm_file_refresh.py`) only validates the caller and the vault name, applies the rate limit and publishes a `PdmFileChangeRequested` event (`source="file_trigger"`) through the transactional outbox; it never reads from PDM itself.
- The route answers `202` once the refresh is queued, `400` when `vault_name` does not match the configured vault, `403` without `use:pdm_addin`, `409` while the integration is off or unconfigured, `422` when neither `file_id` nor `path` was supplied, and `429` once the caller's trigger budget is exhausted.

### 2.2 the batch route

- `POST /api/v1/key/pdm/files/changed/batch` is the same trigger for several files of one operation: `vault_name` plus `files`, 1 to 100 entries of `file_id` (required here) with the optional `path` and `version` hints.
- Each entry may also carry `reason` (`state_change`, `check_in`, `delete`, `move`, `rename`, `resync`, `add`, `copy`; `PdmChangeReason`, any other value is `422`) and `state`, the destination state name of a state change, at most 200 characters. Both travel on the event with the requester's full name and are recorded on the resulting run ([section 2.5](#25-the-pdm-sync-worker)); they change nothing about the refresh itself.
- `RequestPdmFileRefresh.execute_batch` publishes one event per distinct file id, the last entry for an id winning, and commits them together.
- The rate limit counts every file, so a batch that does not fit the remaining budget is rejected whole with `429`; batching saves round trips, not budget.
- The answer is `202 {"accepted": <distinct files>}`, with the error codes of the single route plus `422` for an empty or oversized batch.
- `POST /api/v1/pat/pdm/files/changed/batch` (`src/modules/external_data/adapters/inbound/api/v1/pat/endpoints/pdm.py`) is the same route on the `pat` surface: same body, answer and error codes, signed in with a personal access token that carries `use:pdm_addin`. The token's own scope decides, so a token without it answers `403` even when its owner holds the permission.
- The vault add-in sends all its triggers through the `pat` route, with each Windows user's own token, and resends a batch that failed transiently (Glados unreachable, a timeout, `429`, `502`, `503`, `504`) from an in-memory queue for up to an hour, as described in its README.

### 2.3 the trigger config route

- `GET /api/v1/key/pdm/config` (same file, same `use:pdm_addin` permission) is read-only.
- It returns the configured vault name plus the deduplicated, sorted names of every release-state id in `made_released_state_ids` and `bought_released_state_ids` (`GetPdmTriggerConfig`, `src/modules/external_data/application/use_cases/pdm/get_pdm_trigger_config.py`).
- Each id is resolved to its workflow state name through `IPdmGateway.workflows()`, and an id no workflow currently knows is silently dropped.
- It serves an API-key caller that checks releases itself and needs the release-state names without hardcoding them. The vault add-in does not call it, since PDM transition conditions guard its releases.
- The route answers `403` without `use:pdm_addin` and `409` while the integration is off or unconfigured, and an unreachable or misconfigured vault raises whatever `PdmSessionService` raises, unchanged.

### 2.4 the rate limit

- `PdmTriggerRateLimiter` (`src/modules/external_data/application/services/pdm_trigger_rate_limiter.py`) is an in-process sliding window of 300 files per 60 seconds per actor id.
- A single trigger counts one, and a batch counts each of its files.
- The actor is the one the credential signs in as: an API key's own service account, or the user who owns a personal access token. Each API key therefore has a budget of its own, and with the `pat` route each vault user has theirs, shared by all of that user's tokens.
- It guards against a misbehaving or compromised caller flooding the event stream, not against a precise cross-worker quota, so each Gunicorn worker deliberately holds its own budget instead of sharing one through Redis or a database table.

### 2.5 the pdm sync worker

- The `pdm_sync` Redis Streams consumer group (`_handle_pdm_sync_event` in `src/bootstrap/main.py`, started alongside `notifications`, `webhooks` and `auto_print`) picks up `PdmFileChangeRequested` and runs `RefreshPdmFile` (`src/modules/external_data/application/use_cases/pdm/refresh_pdm_file.py`).
- `RefreshPdmFile` resolves the file fresh from the Web API by id or path, finds its watched folder, skips it if it is in PDM's private state, resolves its kind from the folder (or from the datacard for a `by_kind` folder, with the same disagreement check the poller applies) and hands the result to `IngestPdmFile`.
- It applies the same file type checks the walk applies ([pdm-documents.md section 1](pdm-documents.md#1-the-file-type-rule)) and syncs a file of a `documents` folder as a document.
- The admin Retry action (`RetryPdmFile`) publishes the same event with `source="retry"` instead of calling the HTTP route, so the resulting one-entry run is recorded under trigger `retry` rather than `file_trigger`.
- A file that no longer resolves in PDM, and a file that still resolves but has moved outside every watched folder, are both a deletion for an already linked snapshot: it is marked `missing` and its linked item's `pdm_sync_state` becomes `missing`, the same outcome as the periodic sync's missing sweep.
- Once the file is resolved, `RefreshPdmFile` holds that file's lock (`IPdmFileLock`, a Postgres advisory lock per file id, `adapters/outbound/persistence/pdm_file_lock.py`) for the rest of the refresh.
- A trigger never waits for a whole poll run and is processed as soon as the event arrives; it only waits while a poll worker or another trigger is busy with the same file, and then finds the file already in sync.
- After a successful single-file ingest or document sync, `RefreshPdmFile` resets the folder's cold-folder cadence ([section 3.10](#310-cold-folder-cadence)).
- Write-back runs after the ingest in the same places as in a poll run ([pdm-writeback.md section 3](pdm-writeback.md#3-when-it-runs)).
- The one-entry run records the event's `reason`, `state` and `requested_by_name` as `change_reason`, `change_state` and `requested_by_name`; the admin Retry action sets only the requester.

### 2.6 the file history route

- `POST /api/v1/pat/pdm/files/history` (same file as the `pat` batch route, `ListPdmFileHistory` in `src/modules/external_data/application/use_cases/pdm/list_pdm_file_history.py`) returns the sync run entries of up to 100 files, merged and newest first, at most `limit` of them (default 50, 1 to 200).
- The body is `vault_name` plus `file_ids`; the vault name is checked as the trigger checks it.
- Each entry carries the file's `file_id`, `name`, `path` and `kind`, the entry's `action`, `message` and `created_at`, and its run's `run_id`, `trigger`, `run_started_at`, `run_finished_at`, `run_error`, `change_reason`, `change_state` and `requested_by_name`. No item id and no part data.
- It reads the run log only (`IPdmSyncRunRepository.list_file_history`, served by the `(vault_id, file_id)` index on the entry table), so a trigger still queued or rejected before it was queued has no entry yet, and history older than the retention is gone ([pdm-admin.md section 4](pdm-admin.md#4-the-sync-run-log)).
- It needs `use:pdm_addin`, the PDM add-in preset's permission, since the admin sync log reads sit behind `read:settings`, which no token can hold. It answers `400` for the wrong vault, `403` without the permission, `409` while the integration is off or unconfigured, `422` for an empty or oversized list or a limit out of range, and an empty list while the vault id has not been resolved yet.
- The vault add-in calls it for the files selected in the vault view and shows the answer on its tab.

## 3 the periodic sync

### 3.1 scheduling and run triggers

- `PdmPollScheduler` (`src/bootstrap/workers/pdm_schedule.py`) runs one interval task on each worker's event loop (`src/modules/platform/infrastructure/interval_task.py`), ticking every 60 seconds on every Gunicorn worker, the same shape as the backup scheduler.
- Each tick calls `RunPdmPollIfDue` (`src/modules/external_data/application/use_cases/pdm/run_pdm_poll_if_due.py`), which first checks that the integration is enabled and configured and that `poll_interval_minutes` has elapsed since `last_poll_at`, so most ticks cost almost nothing.
- Only once a poll is due does it take `SqlAlchemyPdmPollLock`'s Postgres advisory lock, so exactly one worker runs `PollPdmVault` for that tick.
- `PollPdmVault` lives in `src/modules/external_data/application/use_cases/pdm/poll_pdm_vault.py`, which holds the order of a run's steps. The steps are its base classes in the sibling modules: the folder walk in `_poll_walk.py`, the diff in `_poll_diff.py`, the dispatch to ingest and document sync in `_poll_dispatch.py`, the missing sweep, conflict retries and cold-folder cadence in `_poll_reconcile.py`, and the run log and progress in `_poll_run.py`.
- `last_poll_at` being `None` means either a vault that was never polled or an admin's "Synchronize with PDM" request having just cleared it through `RequestPdmPoll`.
- To tell the two apart, `RunPdmPollIfDue` checks whether a `scheduled` or `manual` run was ever recorded for the vault: neither means the first poll ever, recorded as trigger `initial`, and either means an admin request, recorded as `manual`.
- An elapsed interval is recorded as `scheduled`.
- A `PdmSyncRun` row is opened before anything else runs, so a crash partway through a scan still leaves a visible, unfinished run in the log.

### 3.2 the folder walk

- Each enabled watched folder's root is found by resolving its configured path fresh every run, one `browse` call per path segment starting from the vault root (id 1), never cached.
- A stored `folder_id` is the fallback for a folder renamed or moved in PDM whose path no longer resolves ([section 3.7](#37-moves-and-renames)).
- The folder is then browsed, and if `recursive`, the walk recurses depth first into every subfolder, cycle safe by folder id, skipping deleted entries.
- `folders_walked` counts every folder whose contents were listed, not the ancestor lookups spent resolving a watched path to its id.
- A subfolder that cannot be browsed is recorded as its own `error` entry and the walk continues elsewhere.
- A failure browsing a watched root, or resolving it to a folder id at all (neither the path nor a stored id works), means nothing was seen under that folder this run, so its missing sweep is skipped too rather than risking a false mass "missing" on one bad call.
- A `made` or `bought` folder only snapshots files with an allowed extension ([pdm-documents.md section 1](pdm-documents.md#1-the-file-type-rule)).

### 3.3 the diff

- Snapshot rows are read per watched folder, never for the whole vault: once a watched root has been walked, the rows whose parent folder is one of the visited folders are read in one batch, plus, by file id, the rows of files found there whose stored parent folder lies elsewhere, so a file that moved in keeps its row and item link.
- A file's snapshot is written only when something changed: the file is new, its version or workflow state id differs from what is stored, its `sync_state` was `pending`, `error` or `missing`, or its kind was just adopted from an explicit folder it moved into while unlinked.
- An unchanged file is left alone entirely: no database write, no ingest call, and no `last_seen_at` update.
- PDM calls always happen before the matching database write: a folder's contents and a changed file's variables are fully fetched before anything is upserted, so a PDM failure mid-scan never leaves a half-written batch.
- A changed file's row is written as `pending` together with its new version, so a run that dies before ingesting it leaves a row the next run still treats as changed.

### 3.4 parallel ingest

- After a folder's diff is stored, its changed files are ingested by up to `ingest_concurrency` workers at once.
- Each worker runs the same per-file stack (variables read, ingest, write-back, thumbnail, run entry) on its own database session, built by the scheduler's worker factory, since one session cannot serve concurrent requests.
- Workers drain a shared list of the folder's files and hold each file's lock while working on it, so the trigger path never ingests the same file at the same time.
- With `ingest_concurrency` at 1, or a folder with a single changed file, the poller ingests on its own session.
- Folder browsing stays sequential.

### 3.5 manual, scheduled and initial runs

- A `manual` run treats every file the walk finds as changed, bypassing the diff, and also skips the reappeared-unchanged shortcut, so it fully re-evaluates everything it sees.
- A linked file at an unchanged version then reaches ingest's version guard ([pdm-ingest.md section 2.6](pdm-ingest.md#26-rule-6-version-guard)), which keeps it linked and in sync rather than reapplying it.
- A `scheduled` run keeps the normal diff, since re-ingesting every watched file on every tick would be needless load.
- An `initial` run needs no forcing: with no snapshot rows yet, every file is new by the normal diff alone.

### 3.6 missing files and reappearance

- Every folder id visited during the walk is recorded against the watched folder it was found under.
- After the walk, every snapshot whose `parent_folder_id` is one of the visited folders, that no folder saw this run and that is not already `missing`, is marked `missing`, and the linked item's `pdm_sync_state` becomes `missing` too.
- Membership is decided by folder id, never by comparing paths, which a rename would silently break.
- The sweep is a set difference over the snapshot rows already read for the walked folders, computed once, not a second database scan.
- A folder whose root browse failed contributes nothing to the sweep.
- A linked file that comes back at the same version and workflow state it had when it went missing is flipped back to `ingested`, and its item to `synced`, without calling ingest again, since nothing could have changed while it was unreachable.
- A file that reappears at a different version or state is an ordinary change and is re-ingested.
- A missing document only moves its snapshot row ([pdm-documents.md section 5](pdm-documents.md#5-replacement-and-missing-files)).

### 3.7 moves and renames

- A watched folder's id is re-resolved from its configured path on every run, so a folder deleted and recreated under the same path in PDM is still walked.
- When the path resolves to a different folder than the stored `folder_id`, the walk follows the path.
- When the path no longer resolves, as after a rename or move in PDM, the walk follows the stored `folder_id`.
- Either disagreement is recorded as an `error` entry on every run until the admin picks the folder again, because the trigger path, pre-release validation and the settings save all match files to watched folders by path and treat the files of a stale path as unwatched.
- With no stored id and no resolvable path, the root resolution fails as described in [section 3.2](#32-the-folder-walk).
- A file that moves between two explicit folders while still unlinked adopts the new folder's kind.

### 3.8 kind conflicts and skips

- An already linked file (its snapshot carries an `item_id`) found under an explicit `made` or `bought` folder whose kind disagrees with the item's resolved kind is parked as a `conflict` ("linked as X, now in a Y folder").
- A `by_kind` folder never triggers that conflict, since its kind always comes from the datacard.
- A file in an explicit folder whose kind variable disagrees with the folder's declared kind is also a `conflict`, resolved before ingest is called; the SolidWorks add-in is the first guard (it locks `Glados.Kind` once written), so this is a backstop.
- A file in a `by_kind` folder with an empty or unrecognised kind variable is `skipped` ("kind not set"), not a conflict, since nothing has gone wrong yet.
- A file whose listing reports a blank workflow state (PDM's private state), or that answers HTTP 403 to a datacard read for any other reason, is `skipped`, never `error`, and clears itself once the file is checked in or the permission granted ([PDM_INTEGRATION.md section 12.2](../PDM_INTEGRATION.md#122-the-vault-user-for-glados)).
- Ingest's own conflicts, the part-number reservation clash and the "already linked under the other kind" guard, are in [pdm-ingest.md section 2](pdm-ingest.md#2-the-rules).

### 3.9 conflict retries

- At the end of every run, every snapshot parked as `conflict` for the vault is retried.
- A retried file is re-read fresh from PDM, never replayed from the stored `parked_payload`, checked again against the folder-kind conflict rule for its current path and, if clear, handed to ingest again.
- A file no longer found in PDM during a retry is marked `missing`.
- This is what lets a renumbering chain or a corrected kind variable converge on its own over a few ticks.
- Conflicted files are re-read from PDM 100 at a time.
- While more than 100 conflicts are parked, a scheduled run skips a conflict whose file is unchanged in PDM (same version and workflow state) and was last attempted less than an hour ago; a manual run always retries all of them.
- A dismissed row has no parked payload and is no longer retried ([pdm-admin.md section 3](pdm-admin.md#3-retry-and-dismiss)).

### 3.10 cold-folder cadence

- Each watched folder has its own walk frequency on top of `poll_interval_minutes`, so Web API load scales with vault activity rather than vault size.
- The state lives in `pdm_folder_poll_state_table`, keyed by vault id and a folder key that is the resolved PDM folder id when set, else the normalised watched path.
- A `scheduled` run skips a folder whose `next_due_at` is in the future entirely, without browsing it, and counts it in `folders_skipped_cold`.
- `manual` and `initial` runs ignore the cadence and walk every enabled folder.
- After a scheduled run, a walked folder with at least one file that was not simply left alone (a new file, a version or state change, a conflict, an error, an ingest-level `skipped`, or a file the missing sweep marked gone) is reset to the base interval.
- A walked folder with nothing but unchanged files advances its unchanged-run streak and gets a new `next_due_at` that doubles per streak step, capped at `poll_interval_minutes` times `cold_folder_max_multiplier`.
- The trigger path resets the same state after a successful single-file ingest or document sync, so a folder a trigger just touched stays warm.
- The cadence is neither consulted nor updated for a folder whose root browse failed this run.

### 3.11 run entries, progress and finish

- One run entry is added per changed file (the ingest outcome's action and message), per file marked missing (`missing`), per folder that could not be browsed (`error`) and per conflict retry.
- Every touched, linked file then goes through write-back and the thumbnail fetch, each committed on its own before the next PDM call.
- While it runs, a poll writes its progress onto its own run row at most every two seconds and only where no other write is pending: `phase` (`walking`, `ingesting`, `finishing`), `current_path`, `files_queued`, `files_processed`, the running counts and `progress_at`.
- An unfinished run whose `progress_at` is older than ten minutes died midway and is no longer reported as running.
- The run row is closed with the final counts (`files_seen`, `changed`, `ingested`, `skipped`, `conflicts`, `errors`, `missing`, `folders_walked`, `folders_skipped_cold`) and a one-line summary, and runs older than 30 days are pruned, whether the run succeeded or failed partway.
- `GET /metrics` exposes the run log, the snapshot table and the cold-folder state as Prometheus gauges: poll success and failure and add-in trigger timestamps, the newest run's counters, file counts by `sync_state`, reconciliation finding counts by category, and the cold-folder count. [operations-monitoring.md section 3](operations-monitoring.md#3-metrics) lists them with suggested alert rules.

### 3.12 database cost

- A run reads only the snapshot rows of the folders it walked.
- Every batch read or write by file id or folder id is split into `IN` queries of at most 1,000 values.
- Lookups by parent folder and by lower-cased file name are backed by the indexes `ix_pdm_file_snapshot_vault_parent_folder` and `ix_pdm_file_snapshot_vault_name_lower`.
