# pdm integration

- [pdm integration](#pdm-integration)
  - [1 purpose and scope](#1-purpose-and-scope)
  - [2 components and data flow](#2-components-and-data-flow)
  - [3 configuration](#3-configuration)
  - [4 the two sync paths](#4-the-two-sync-paths)
    - [4.1 the trigger path](#41-the-trigger-path)
    - [4.2 the periodic sync](#42-the-periodic-sync)
    - [4.3 pre-release validation](#43-pre-release-validation)
    - [4.4 required fields](#44-required-fields)
  - [5 ingest rules](#5-ingest-rules)
  - [6 ownership enforcement in the web](#6-ownership-enforcement-in-the-web)
  - [7 observability and administration](#7-observability-and-administration)
  - [8 limits and open points](#8-limits-and-open-points)
  - [9 database changes](#9-database-changes)
  - [10 write-back to PDM](#10-write-back-to-pdm)
  - [11 documents and thumbnails](#11-documents-and-thumbnails)
    - [11.1 the file type rule](#111-the-file-type-rule)
    - [11.2 the `documents` watched folder](#112-the-documents-watched-folder)
    - [11.3 categories and storage](#113-categories-and-storage)
    - [11.4 replacement and missing files](#114-replacement-and-missing-files)
    - [11.5 thumbnails](#115-thumbnails)
  - [12 what the PDM vault must provide](#12-what-the-pdm-vault-must-provide)
    - [12.1 the PDM Web API server](#121-the-pdm-web-api-server)
    - [12.2 the vault user for Glados](#122-the-vault-user-for-glados)
    - [12.3 folders](#123-folders)
    - [12.4 variables and data card](#124-variables-and-data-card)
    - [12.5 workflows](#125-workflows)
    - [12.6 part numbering](#126-part-numbering)
    - [12.7 numbering and kind, PDM-side setup](#127-numbering-and-kind-pdm-side-setup)
    - [12.8 what is not required](#128-what-is-not-required)
  - [13 reconciliation report](#13-reconciliation-report)
  - [14 catalogue preview](#14-catalogue-preview)

## 1 purpose and scope

SolidWorks PDM is the system of record for CAD data. Glados is the catalogue and production-planning system downstream of it: a made or bought item that carries a CAD model is born from a file in the vault, and every field PDM owns for that item is read from the vault, never typed into Glados by hand. [FIELD_OWNERSHIP.md](FIELD_OWNERSHIP.md) states which system owns which value; this guide describes the machinery that implements those rules: the settings, the two paths that discover a change, the ingest that applies it, and the admin surfaces that show what happened.

Glados reads from the vault's Web API: folder listings, file identity (`PDM.PartNumber`, `PDM.Revision`), datacard variables mapped to catalogue fields and workflow state. It never writes catalogue data back into PDM and never transitions a file's workflow state. The one write path, write-back (section 10), is opt-in and limited to three version-free datacard variables that mirror Glados' sync status onto the file; ingest never reads them back. Outside it, the only way a mutating call reaches the vault is an admin deliberately using the Web API console with its critical-endpoint switch on, and that call is recorded in the settings audit log.

Three separate programs are involved:

1. **The PDM Web API server**, SOLIDWORKS PDM Professional's own Web API 2, running against the vault (default port 65453). Glados is a client of it; nothing in this repository runs on the PDM server.
2. **The SolidWorks add-in** ([`glados-sw-addin`](https://github.com/deloarts/glados-sw-addin), a separate repository) runs inside SolidWorks at the engineer's workstation and writes the `Glados.*` custom properties on the open document from values it fetched through the `pat` API. It never creates a made or bought item, never pushes their field values into Glados and never links a document to an item; its token preset (`SOLIDWORKS_ADDIN_SCOPES` in `src/modules/platform/domain/services/token_permission_rules.py`) holds `write:source_items` and `use:data_portal`. The first makes creating a source item the only write it can make, and the second opens its EPLAN Data Portal lookups. When it connects it calls `GET /api/v1/pat/version`, and when the `pat` contract minor there is not one it supports, it shows a warning that names the server's version and the contract it supports, then keeps working ([RELEASING.md section 1.1](RELEASING.md#11-how-a-client-checks-the-backend-it-talks-to)).
3. **The vault add-in** ([`glados-pdm-addin`](https://github.com/deloarts/glados-pdm-addin), a separate repository), a program that hooks the vault's own events on the client that performs a check-in or a workflow transition. Each Windows user signs in on its Glados tab in File Explorer with their own personal access token, scoped to `use:pdm_addin` (`PDM_ADDIN_SCOPES` in the same module, the **Create PDM Add-in Token** preset on the account page). With it the add-in reports changed files so Glados ingests them at once (section 4.1), and shows on its tab what Glados did with the files the user selects, read from the sync run log. It never validates a file and never blocks a transition; PDM transition conditions guard releases (section 4.3). It checks the server's `pat` contract on connect the same way as the SolidWorks add-in. The periodic poller (section 4.2) still covers every change the vault add-in does not report.

## 2 components and data flow

**The settings row.** Everything the integration needs lives on one singleton row, `admin_pdm_settings` (`AdminPdmSettings`). `is_pdm_enabled()` (enabled and fully configured) is the gate every other part checks before doing anything.

**The session.** PDM's authentication opens a server-side session with no expiry and no logout, and each authentication is likely a license seat, so one bearer token is cached on the settings row and shared by every worker. `PdmSessionService` is the single seam every use case calls through; it re-authenticates and retries once when PDM drops the session.

**The gateway and the operation catalogue.** `HttpxPdmGateway` is the one adapter that speaks HTTP to the vault, with a typed method per call the codebase uses. A generated catalogue of the full Web API surface backs an admin console for troubleshooting.

**Ingest.** `IngestPdmFile` applies one already-fetched file's variables to a made or bought item. It never talks to PDM for the file itself and always runs as the system user (section 5).

**The poller.** `PollPdmVault` is the baseline sync: on a due tick it walks every enabled watched folder, diffs what it finds against the snapshot table and hands whatever changed to ingest. A 60-second scheduler tick on every worker decides whether a poll is due (section 4.2).

**The trigger endpoint and the `pdm_sync` worker.** The vault add-in's change notification only stages an event; a dedicated Redis Streams consumer group re-reads the file from PDM and hands it to the same ingest (section 4.1).

**The snapshot table.** `pdm_file_snapshot_table` holds one row per watched file: its scan metadata, where it stands in the poll-to-ingest pipeline (`sync_state`) and, for a parked conflict, the blocked payload. It is both the poller's diff base and the source of the admin "PDM files" list.

**The sync run log.** One row per poll tick, single-file refresh or reconciliation report, with one entry per file the run touched. It backs the sync log dialog and the vault add-in's file history, and keeps 30 days of runs. A single-file refresh also records why its caller said the file changed and who asked.

**The admin API console.** Any catalogued operation can be called ad hoc through the same session service. Mutating operations stay off unless the deployment sets `PDM__ALLOW_MUTATING_OPERATIONS=true`; even then each call needs an explicit per-call switch, and every one that succeeds is audited.

Both sync paths converge on the same ingest step:

```
vault add-in / API key / admin Retry --> POST /files/changed(/batch)
    or the Retry action --> RequestPdmFileRefresh / RetryPdmFile --> transactional
    outbox --> pdm_sync worker --> RefreshPdmFile --> IngestPdmFile

PdmPollScheduler tick (60s) --> RunPdmPollIfDue --> PollPdmVault
    (folder walk, diff) --> IngestPdmFile (per changed file)
```

Both paths write the item, the snapshot row and a sync run entry, and publish a `PdmFileIngested` or `PdmIngestConflict` domain event.

Full rules: [reference/pdm-sync.md](reference/pdm-sync.md) for the session, [reference/pdm-admin.md](reference/pdm-admin.md) for the gateway, the catalogue and the console.

## 3 configuration

Everything is set under *Settings → SolidWorks PDM*, which reads and writes `/api/v1/web/admin/settings/pdm`. "Test connection" probes an unsaved connection without storing anything, so a bad configuration is caught before the integration is switched on, and switching it on is refused until a connection, an enabled watched folder and a released state exist.

| Setting | What it does |
|---|---|
| Connection | Base URL, vault name, service account, certificate verification and timeout. |
| Datacard variable maps | One map per kind from Glados field to datacard variable; an unmapped field is never touched. |
| Required fields | Fields a file must carry before ingest creates a row, on top of a locked set (section 4.4). |
| Watched folders | The vault folders the poller walks, each `made`, `bought`, `by_kind` or `documents`. |
| Lifecycle states | Per kind, the workflow states that mean released, obsolete and replaced. |
| Poll interval, cold-folder multiplier, ingest concurrency | How often the vault is walked, how far quiet folders back off, and how many files are ingested at once. |
| *CAD items read-only* | Whether PDM-owned fields are actually locked in the web (section 6). |
| Write-back, thumbnails, documents | The opt-in features of sections 10 and 11. |
| Approver from PDM | Whether ingest also sets `approver_id` from the releaser (section 5). |
| Stuck after days | The reconciliation report's threshold (section 13). |

A `by_kind` folder reads each file's kind from a datacard variable (`Glados.Kind` by default); a `made` or `bought` folder asserts the kind directly. The external part-number pattern that PDM numbers must match is not a PDM setting but lives on *Settings → Numbering*, one regex per kind.

Saving a change to the maps, the state lists or the watched folders requeues every skipped file, so a skip caused by a setting clears once the setting changes.

Full rules: [reference/pdm-settings.md](reference/pdm-settings.md).

## 4 the two sync paths

Every change reaches the catalogue through one of two paths, and both end at the same `IngestPdmFile` call.

### 4.1 the trigger path

The vault add-in calls `POST /api/v1/pat/pdm/files/changed/batch` with the signed-in user's personal access token, which carries `use:pdm_addin` and nothing else. Each file may say why it changed (a state change and its destination state, a check-in, a delete, a move, a rename, a file added already checked in, a copy or a manual resync), which only labels the file's history. Other callers, such as the Dispatch action below, use `POST /api/v1/key/pdm/files/changed` (or its batch form) with an API key of the same scope. The route trusts nothing in the request beyond which file is meant: it checks the vault name, applies a per-caller rate limit and stages a `PdmFileChangeRequested` event through the transactional outbox. The `pdm_sync` worker then re-reads the file from the Web API, finds its watched folder and kind, and hands it to ingest. A file that no longer resolves, or has moved outside every watched folder, is marked `missing`. The admin Retry action publishes the same event.

A trigger only exists where something sends one. A change made by a client without the vault add-in, such as a workstation that missed the rollout, a scripted or API check-in, or a Web2 upload, reaches Glados through the periodic sync alone.

Where the vault add-in is not installed, PDM's Dispatch add-in can make the same call without any code: a Dispatch action on "after state change" that shell-executes

```
curl.exe -s -m 5 -X POST https://<glados-host>/api/v1/key/pdm/files/changed
  -H "X-Api-Key: <api key with use:pdm_addin>"
  -H "Content-Type: application/json"
  -d "{\"vault_name\":\"<vault>\",\"path\":\"%PathToSelectedFile%\"}"
```

The action runs on the client that performs the transition, so every workstation needs HTTPS access to the Glados backend and `curl.exe` (part of Windows 10 and later). The API key is visible to every vault user, which is why it may carry nothing but `use:pdm_addin`. Failures are silent, and the periodic sync covers them.

Full rules: [reference/pdm-sync.md section 2](reference/pdm-sync.md#2-the-trigger-path).

### 4.2 the periodic sync

A scheduler ticks every 60 seconds on every worker, but a tick only polls once the poll interval has elapsed (or an admin pressed "Synchronize with PDM"), and an advisory lock lets exactly one worker run it. The poller walks each enabled watched folder from the vault root, resolving the configured path fresh every run, compares what it finds with the snapshot table, and ingests only the files that changed, several at once. A manual run treats every file as changed.

Around that core sit a few safety rules. A file no longer seen in a folder that was walked successfully is marked `missing`, decided by folder id so a rename cannot fake a mass deletion, and a folder that failed to browse marks nothing. A linked file found in a folder of the other kind is parked as a conflict. Parked conflicts are re-read from PDM at the end of every run, which lets a renumbering chain converge on its own. A folder with no changes across several runs is walked less often, up to the poll interval times the cold-folder multiplier, so Web API load follows vault activity rather than vault size.

The walk's cost tracks the number of folders browsed, not files found, and PDM returns every child of a folder in one response. For a watched folder that grows indefinitely (a "released parts" folder, say), split it by time, one subfolder per month of releases, and keep the watched folder recursive. That trades a few cheap extra folder calls for keeping every single response bounded, which matters given the Web API limits in section 8.

Full rules: [reference/pdm-sync.md section 3](reference/pdm-sync.md#3-the-periodic-sync).

### 4.3 pre-release validation

Both sync paths only ingest a file once it is released, so a data problem (a missing manufacturer, an unresolved reference, a part number the other catalogue already claimed) normally surfaces only afterwards, on the "PDM files" list. Pre-release validation answers the same question just before the transition: `ValidatePdmPayload` is a read-only dry run of ingest's rules that evaluates every rule, writes nothing and reports what the real ingest would do (`would`: `created`, `revised`, `updated`, `claimed` or `unknown`).

The SolidWorks add-in's check button calls `POST /api/v1/pat/pdm/validate` with the document's own property values, as advice before a save. The API-key routes `POST {API_KEY}/pdm/files/{file_id}/validate` and its batch form read the file from PDM instead and serve a caller that checks a file in the vault, such as a script; the vault add-in does not call them. Fields the release workflow will assign (the part number and revision) are expected to be blank before release, so they are reported as `pending_pdm` rather than as problems. Glados never blocks a state transition itself. Releases are guarded in the PDM workflow, with transition conditions on the datacard variables Glados needs and permissions on who may release, and a rule only Glados can judge shows up after the release on the "PDM files" list and in the sync log.

Full rules: [reference/pdm-ingest.md section 8](reference/pdm-ingest.md#8-pre-release-validation).

### 4.4 required fields

Some fields gate whether ingest may create a row at all. A locked set is always enforced: `part_number` and `article_name` for both kinds, `revision` for made items, and `order_code_1` and `manufacturer_id` for bought items. On top of that, an admin can mark any other mappable field required, plus the `fabrication_step` pseudo-rule for made items; the defaults are `material` and `fabrication_step` for made items and `revision` for bought items. A file that misses one is skipped with a message naming the fields; an in-place update of an existing row is never checked.

Full rules: [reference/pdm-ingest.md section 7](reference/pdm-ingest.md#7-required-fields).

## 5 ingest rules

`IngestPdmFile` applies one file in a fixed sequence of numbered rules, which the code comments refer to by number: the workflow state decides the target status (1), the identity variables must be present (2), a file linked under the other kind is a conflict (3), the part number must match the external pattern (4), raw datacard strings are coerced without ever raising (5), an older or already applied version is skipped (6), an obsolete or replaced state only flips the status (7), and then made items are created, revised or updated in place (8) and bought items created, claimed or updated in place (9). Every outcome updates the snapshot row (10), and a write or a parked conflict publishes an event (11).

A business condition never raises: a mismatch, a stale version or a clash comes back as a normal `skipped` or `conflict` outcome, so a poll run keeps going. Every write, including creating a new item or revision through the same use cases the web uses, happens in one transaction per file, so a crash leaves either nothing or a fully linked row.

PDM owns a linked row's part number: when the file's number changes, ingest renumbers the linked rows and keeps the old number registered, or parks a conflict when the new number belongs to another item. On a release or status change, ingest reads the file's workflow history to attribute the change to the Glados user who released it, using links an admin confirms in the "Match PDM Users" dialog.

Full rules: [reference/pdm-ingest.md](reference/pdm-ingest.md).

## 6 ownership enforcement in the web

On a CAD-owned row, the web and PAT may not change a field that PDM or the add-in owns, including `status`, which follows the workflow state. The check runs in the update use cases, not in the routes, and applies only while the integration is enabled and *CAD items read-only* is on; an admin can switch that off in an emergency without changing ownership, and the next ingest overwrites as usual. Ingest itself runs as the system user and is exempt. Dual-owned fields stay editable, and a successor can only be assigned to a CAD row once PDM has moved it to a replaced state. The frontend disables the same fields from a server-computed list, but the server check is authoritative.

Full rules: [reference/field-ownership.md section 6](reference/field-ownership.md#6-enforcement).

## 7 observability and administration

The admin routes live under `/api/v1/web/admin/settings/pdm` and need `read:settings` to read and `write:settings` to change anything. The settings tab offers "Synchronize with PDM", which shows what the sync is doing right now, the sync run log, and the "PDM files" list with one row per file ever seen under a watched folder:

| `sync_state` | Meaning | What to do |
|---|---|---|
| `pending` | Seen, not yet ingested (a fresh row, or one just reset by Retry). | Wait for the next poll or trigger. |
| `ingested` | Applied successfully; `part_number`, `revision` and `item_id` are set. | Nothing; this is the steady state. |
| `skipped` | A state, identity or pattern mismatch (rules 1, 2 and 4) or a private-state or permission gap. | Usually nothing; fix the setting or the PDM permission if it persists. |
| `missing` | Not seen by the last successful walk of its folder. | Check the file still exists under a watched folder in PDM. |
| `conflict` | Parked: a part-number clash, an unresolved reference or a kind disagreement. | Resolve the clash in PDM or in Glados (merge or renumber), then Retry, or Dismiss to stop the automatic retries. |
| `error` | A repository or transport failure while processing the file. | Check `last_error`; it usually resolves itself on the next attempt. |

Retry re-reads the file from PDM; Dismiss drops a parked conflict and marks it skipped without contacting PDM. Settings changes, manual polls, Retry, Dismiss and successful mutating console calls are written to the settings audit log.

Full rules: [reference/pdm-admin.md](reference/pdm-admin.md).

## 8 limits and open points

**PDM Web API constraints.** `browse`, `searchvariables` and `files/info` take no page size or cursor, and Glados never pages them; the Web API has no documented pagination and no documented result cap. The legacy PDM web search UI's 100-result default belongs to that separate client and does not limit what a `browse` or `search` response returns here. The folder walk is built around that absence: keeping each watched folder's file count bounded keeps each `browse` response small, which matters because a response an IIS-hosted Web API server refuses to return (its own configured size cap) would fail a whole folder rather than degrade gracefully. The console's 512 KiB preview truncation is Glados' own display limit and says nothing about that cap.

**Bulk-edit panels do not lock PDM-owned fields.** The single-item edit dialogs (`MadeItemDetailDialog.vue` and its bought-item equivalent) combine the web revision-policy lock with the PDM-ownership lock (`isPdmLockedField`). The catalogue bulk-edit forms (`MadeItemsCatalogueEdit.vue`, `BoughtItemsCatalogueEdit.vue`) only apply the revision-policy lock, so a field disabled on a CAD-owned item's own dialog is not disabled when that item is part of a bulk edit. The server-side check still rejects the write, so no PDM-owned data can be corrupted, but the user only learns why after submitting.

**No live refresh in the "PDM files" dialog.** It relies on its sync button and its own polling rather than a push signal.

## 9 database changes

The integration keeps its state in these tables of the `external_data` module: `admin_pdm_settings` (the connection, the watched folders, the variable maps and the write-back switch), `pdm_file_snapshot_table` (the last state Glados saw of each file), `pdm_folder_poll_state_table` (the walk cadence per folder), `pdm_sync_run_table` and `pdm_sync_run_entry_table` (the run log), `pdm_reconciliation_finding_table` (the findings of a reconciliation) and `pdm_document_link_table` (vault documents linked to item files).

On the catalogue side, made and bought items carry `data_source`, `vault_id`, `pdm_file_id`, `pdm_file_version`, `pdm_synced_at` and `pdm_sync_state`, and made items also `pdm_source_item_id`. `part_number_registry` keeps a part number with the catalogue that holds it. The persistence models hold the exact columns, and [reference/development-migrations.md](reference/development-migrations.md) describes how a migration changes them.

## 10 write-back to PDM

Write-back lets PDM users and the SolidWorks add-in see a file's Glados status without querying Glados. After every ingest of a linked file, `PdmWriteBack` writes three version-free datacard variables: `Glados.Ids` (the Glados rows of the file's family), `Glados.NewestRevisionSyncState` (`synced`, or the conflict or skip reason) and `Glados.NewestRevisionSyncedAt`. It writes only those three, never transitions a workflow state, and ingest never reads them back. It is off by default (`writeback_enabled`), and a write-back failure is recorded in the run log but can never fail the ingest it follows; the next touch of the file retries it.

Before enabling it on a production vault:

1. Create the three variables on the file card as text (or an equivalent free-text type), marked version-free, as listed in section 12.4.
2. Decide whether to mark them "Update all versions"; with the flag the write reaches every configuration of the file, without it only the `@` (file-level) configuration, which is what a typical single-configuration part or assembly needs.
3. Map the three fields to the same variable names in both the made and the bought map.
4. Through the admin API console, probe a `GET` and then a `POST` datacard call against one test file, to confirm the write-all-configurations behaviour matches the configuration and that a version-free write does not create a new file version, which the Web API documentation does not guarantee explicitly.

No PDM permission beyond the existing datacard-edit right on the file's workflow states is needed, since these variables are not gated by state the way a transition is.

Full rules: [reference/pdm-writeback.md](reference/pdm-writeback.md).

## 11 documents and thumbnails

Two more concerns build on the same folder walk and refresh machinery: a file-extension gate on the made and bought folders, and a `documents` watched folder whose files are never catalogue items but exported drawings and models attached to an existing one. Both live in `application/use_cases/pdm/pdm_documents.py`.

### 11.1 the file type rule

Each kind has a list of allowed extensions (made `sldprt`, bought `sldprt` and `sldasm` by default). A `made` or `bought` folder ignores every other file without snapshotting it and only counts it in the poll summary; a `by_kind` folder admits both lists and skips a file whose extension does not fit the kind its datacard names.

Full rules: [reference/pdm-documents.md section 1](reference/pdm-documents.md#1-the-file-type-rule).

### 11.2 the `documents` watched folder

A `documents` folder ("Exported Documents") is a vault folder a PDM task publishes drawings, DXF or STEP exports into. Its files are matched to an existing made or bought item, by the file's datacard variables or by a regular expression on the file name, and attached to it. They are synced only while in one of the document released states, a vault-wide list separate from the CAD workflow.

Full rules: [reference/pdm-documents.md section 2](reference/pdm-documents.md#2-the-documents-watched-folder).

### 11.3 categories and storage

The document's extension picks the item file category (by default PDF to drawing, DXF to dxf, STEP to step), and the file is stored through the same upload use case as a web upload. An image can instead be mapped to become the item's CAD rendering picture.

Full rules: [reference/pdm-documents.md section 3](reference/pdm-documents.md#3-categories).

### 11.4 replacement and missing files

A changed export replaces the earlier file, because drawing, DXF and STEP are single-file categories. A document that disappears from the vault only marks its snapshot `missing`; the attached file and the item's own sync state stay as they are.

Full rules: [reference/pdm-documents.md section 5](reference/pdm-documents.md#5-replacement-and-missing-files).

### 11.5 thumbnails

When `thumbnails_enabled` is on (default off), each successful ingest also fetches the file's PDM check-in thumbnail and stores it as the item's CAD rendering, unless an exported image already supplied one. Most vaults need PDM's **Convert task** configured to render a thumbnail on check-in before there is anything to fetch; a file without one is a quiet no-op.

Full rules: [reference/pdm-documents.md section 6](reference/pdm-documents.md#6-thumbnails).

## 12 what the PDM vault must provide

This section is the minimum-requirements checklist for whoever administers the PDM vault: what must exist on the PDM side for the integration to work, and nothing more. Every item traces to a concrete call the backend makes or a check ingest, the settings save or write-back performs. Where PDM's permission model has a name this guide states with confidence, that name is used; otherwise the required capability is described, so the administrator can map it onto whatever the vault's permission model calls it.

Two things share the word "property" here. A vault variable is a data card field, defined in the PDM database and read or written through the Web API; it is the only thing Glados touches. A custom property is a value stored on the SolidWorks document; the SolidWorks add-in writes these, and PDM's own variable-to-property mapping, configured in the PDM Administration tool, makes a document's custom property show up as a vault variable on the data card. Glados never writes a custom property and never talks to a SolidWorks document.

### 12.1 the PDM Web API server

A running SOLIDWORKS PDM Professional Web API server (Web API 2, default port 65453) with the target vault added to it, reachable from the Glados backend over HTTP or HTTPS. Base URL, vault name and the vault user's credentials are entered once under *Settings → SolidWorks PDM*. Nothing from this repository runs on the PDM server itself.

### 12.2 the vault user for Glados

A dedicated PDM user for Glados to authenticate as. It needs:

- Enough vault-wide read access to authenticate, read the vault properties (`vault_info`) and list the vault's workflows and their states (`workflows`), which fill the state pickers (section 12.5).
- The right to browse every watched folder (section 12.3), since both the poll and the single-file refresh browse down from the vault root (`browse_folder`). A folder the user cannot browse is a walk error in the sync run log, and a failure on a watched folder's own root skips its whole tree for that run.
- PDM's *Read file contents* and *Show working versions of files* state permissions on every workflow state a watched file can be in, including the released, obsolete and replaced states. A file in a state without them answers HTTP 403 to a datacard read, which Glados records as `skipped`, not `error`, and which clears itself once the permission is granted. *Read file contents* also covers the file's transition history (used for releaser attribution), the thumbnail and the document download.
- If write-back is turned on (section 10), the right to edit the data card variables of checked-in files in those same states.
- The right to list vault users and read a user's extended info (`GET .../users`, `GET .../users/{userId}/Extended`), for matching PDM users to Glados users (section 5).

A file added to the vault but never checked in sits in PDM's private state: the folder listing shows it with a blank workflow state and a datacard read answers 403. Glados skips it the same way until it is checked in, without any admin action.

Glados never transitions a file's workflow state and never checks a file in or out. Outside write-back, nothing in the poller, the trigger path or ingest calls a mutating Web API operation, so the vault user needs no permission to move files between states, check them in or out, or delete anything.

### 12.3 folders

At least one enabled watched folder is required before the integration can be switched on. Each entry names a vault-relative path, a kind and whether subfolders are included:

- A `made` or `bought` folder asserts that kind for every file under it.
- A `by_kind` folder reads the kind from each file's kind variable (`Glados.Kind` by default), which must be exactly `made` or `bought`; anything else, a blank value included, is skipped as "kind not set".
- A `documents` folder (section 11) holds exported drawings, DXF or STEP files for Glados to attach to an existing item, and needs only the identity variables or file name pattern its matching setting reads.

Adding, removing or reconfiguring a watched folder happens entirely in Glados' settings; nothing changes on the PDM side beyond the read access in section 12.2.

### 12.4 variables and data card

Every variable named below is Glados' default; each can be renamed independently in the two field-mapping tables of the settings, and what must exist on the card is a variable under the name that mapping lists. An empty mapping means the field is never read (or, for the write-back variables, never written), and ingest never rejects a file over a field it was not asked to read.

The part number, revision and article name variables are needed to ingest anything; for bought items the revision is required by default but configurable, and creating or claiming a bought item also needs the manufacturer id and order code 1, which an in-place update of an already linked bought item does not. `Glados.Kind` is needed only for `by_kind` folders. Everything else is optional unless an admin marks it required (section 4.4), as `Glados.Material` is by default. A `documents` folder's datacard matching needs nothing beyond part number, revision and kind, and thumbnails need nothing on the card.

| Variable (default name) | Needed for | Required | Value format | Written by | Version-free |
|---|---|---|---|---|---|
| `PDM.PartNumber` | made, bought | Yes, identity | Text matching the external part number pattern (section 12.6) | PDM (vault numbering, or an engineer types it) | not required |
| `PDM.Revision` | made, bought | Made: yes, identity. Bought: by default, configurable | Text, the controlled revision label, not the check-in version counter | PDM (the vault's own revisioning) | not required |
| `Glados.Kind` | made, bought | Yes, `by_kind` folders only | Exactly `made` or `bought` | SolidWorks add-in (custom property, write-once) | not required |
| `Glados.ManufacturerId` | bought | Yes, to create or claim a bought item | A single integer, a Glados supplier id | SolidWorks add-in (custom property) | not required |
| `Glados.ArticleName` | made, bought | Yes | Text | SolidWorks add-in (custom property) | not required |
| `Glados.Material` | made | By default, configurable | Text, an ISO material number | SolidWorks add-in (custom property) | not required |
| `Glados.Mass` | made, bought | No | Integer grams; comma or dot accepted as the decimal separator | SolidWorks add-in (custom property) | not required |
| `Glados.BaseSize` | made | No | Text | SolidWorks add-in (custom property) | not required |
| `PDM.RevisionDate` | made | No | ISO (`YYYY-MM-DD`) or German (`DD.MM.YYYY`) date | PDM or an engineer, directly on the card | not required |
| `PDM.RevisionNote` | made | No | Text | PDM or an engineer, directly on the card | not required |
| `Glados.Note` | made, bought | No | Text | SolidWorks add-in (custom property) | not required |
| `Glados.Weblink` | made, bought | No | Text, a URL | SolidWorks add-in (custom property) | not required |
| `Glados.ArticleGroupIds` | made, bought | No | Comma-separated Glados article group ids; an unknown id is dropped, not rejected | SolidWorks add-in (custom property) | not required |
| `Glados.BoughtItemId` | made | No | A single integer, a Glados bought item id; dropped silently if it does not resolve | SolidWorks add-in (custom property) | not required |
| `Glados.SourceItemId` | made | No | A single integer, a Glados source item id; dropped silently if it does not resolve | SolidWorks add-in or web, dual-owned | not required |
| `Glados.Processes` | made | No | Single-line JSON array, the add-in's routing-step encoding | SolidWorks add-in (custom property) | not required |
| `Glados.OrderCode1` | bought | Yes, to create or claim a bought item | Text | SolidWorks add-in (custom property) | not required |
| `Glados.OrderCode2` | bought | No | Text | SolidWorks add-in (custom property) | not required |
| `Glados.Gtin` | bought | No | Text | SolidWorks add-in (custom property) | not required |
| `Glados.Ean` | bought | No | Text | SolidWorks add-in (custom property) | not required |
| `Glados.TariffNumber` | bought | No | Text | SolidWorks add-in (custom property) | not required |
| `Glados.ArticleGroupNames` | made, bought | No | Text, a label next to `Glados.ArticleGroupIds` | SolidWorks add-in (custom property) | not required |
| `Glados.ManufacturerName` | bought | No | Text, a label next to `Glados.ManufacturerId` | SolidWorks add-in (custom property) | not required |
| `Glados.ProcessNames` | made | No | Text, a label next to `Glados.Processes` | SolidWorks add-in (custom property) | not required |
| `Glados.SourceItemName` | made | No | Text, a label next to `Glados.SourceItemId` | SolidWorks add-in (custom property) | not required |
| `Glados.FeatureTreeRepresentation` | made, bought | No | Text, the feature-tree template with its `$PRP` links resolved by SolidWorks | SolidWorks add-in (custom property) | not required |
| `Glados.Ids` | made, bought | Only with write-back | Single-line JSON array | Glados (write-back only, section 10) | Yes |
| `Glados.NewestRevisionSyncState` | made, bought | Only with write-back | Text | Glados (write-back only) | Yes |
| `Glados.NewestRevisionSyncedAt` | made, bought | Only with write-back | ISO 8601 UTC timestamp | Glados (write-back only) | Yes |

The three write-back variables must exist on the card as text (or an equivalent free-text type) and be marked version-free in the PDM Administration tool; write-back refuses to write, and records an error in the sync run log, the moment one is missing from the file-level configuration or is not version-free. The "update all versions" flag is optional (section 10). None of the three needs a custom-property mapping, since Glados writes the vault variable directly and the SolidWorks add-in never touches them.

The SolidWorks add-in writes the `Glados.*` custom properties for made and bought items alike, including the made-item routing in `Glados.Processes`; the `PDM.*` properties are written by the vault only. The label variables and `Glados.FeatureTreeRepresentation` exist only so data cards, BOMs and PDM search can show names or a summary instead of raw ids, and ingest never reads them back ([FIELD_OWNERSHIP.md section 9](FIELD_OWNERSHIP.md#9-label-properties-and-the-feature-tree-template)). The data card shows `Glados.FeatureTreeRepresentation` with its links already resolved, so make its control there read-only: typing into it would replace the links in the custom property with literal text.

### 12.5 workflows

At least one released state, for made or bought items, must be configured before the integration can be switched on; the obsolete and replaced states are optional, per kind. All of them are picked by name from the workflows and states the vault itself reports, so the PDM administrator never hands Glados a state id. A file whose state is in none of its kind's three lists is skipped. Glados only reads the state a file is in; moving a file between states, including into a released, obsolete or replaced state, remains something a PDM user does.

### 12.6 part numbering

Beyond the identity variables, PDM is not asked to number anything in a special way. Whatever produces `PDM.PartNumber`, PDM's numbering scheme or an engineer typing it, must yield text that fully matches the external pattern configured under *Settings → Numbering*, one regex per kind. A part number that does not match is skipped, and an empty pattern skips every file of that kind. No other PDM-side numbering configuration, template or naming convention is required.

### 12.7 numbering and kind, PDM-side setup

Section 12.6 states what Glados checks; this part is guidance for producing a usable number and kind inside the vault. The setup is the PDM administrator's decision, and none of it beyond the pattern match is enforced or seen by Glados.

1. **The number expresses kind, not CAD file type.** The part number says whether the item is made or bought, not whether the SolidWorks document is a part or an assembly. A bought item can be a single part or an assembly the vendor modelled but sells as one article (a cylinder, say); a made item can be a single part or an assembly of made parts (a welded frame). Glados only checks the number against the kind's pattern, and the two patterns may be identical ([FIELD_OWNERSHIP.md section 1](FIELD_OWNERSHIP.md#1-principles)).
2. **The number has to exist at file creation.** Because the file name is the part number in this vault, a serial number generator bound as a card default fires once, when the file is created, and a default can only be scoped by card, that is by SolidWorks file type, never by kind. The recommended setup is a PDM template per kind, for example "New Made Part" and "New Bought Part" for parts and "New Assembly" for an assembly: each uses its own serial number generator to set both the file name and `PDM.PartNumber`, copies the matching SolidWorks template file, and sets the card variable `Glados.Kind` to `made` or `bought`. The vault's variable-to-property mapping carries that value onto the file's custom property, and the SolidWorks add-in reads it to preselect and lock its kind dropdown. Once the per-kind templates exist, the generic part and assembly cards should carry no serial default, so a file created outside them gets no part number rather than one from the wrong kind's sequence.
3. **Imported vendor models.** A vendor STEP file converted to an SLDASM needs the same treatment: either a template that imports into the vendor folder and applies the bought serial number and kind, or a Dispatch rule that fires on add to that folder and assigns both.
4. **Alternatives.** A single kind-neutral serial number generator can number every new file if the numbers are non-significant and both Glados patterns are identical; `Glados.Kind` then still has to be set some other way. Alternatively the number can be assigned at the release transition through a conditional "Set variable" action driven by a serial number generator and conditioned on `Glados.Kind`, which only works where the file name does not already have to be the part number.
5. **Purchased assemblies and their children.** `Glados.Kind = bought` on a purchased assembly's own card is the make-or-buy flag; the files under it must not carry a bought part number or a kind of their own. A `by_kind` folder resolves kind per file, so a child without one is skipped as "kind not set", never ingested under the parent's kind. To keep the CAD bill of materials and Glados agreeing, set SolidWorks' configuration option "Child component display when used as subassembly" to "Hide" on purchased assemblies.

### 12.8 what is not required

- No program needs to run on the PDM server itself, since Glados only calls the Web API remotely. The vault add-in is optional; without it, changes arrive through the periodic sync alone.
- No PDM webhook needs to be registered. The Web API's webhook operations are reachable through the admin console, but no sync path uses them and PDM is never asked to call Glados; discovery is Glados polling and the trigger route the vault add-in calls.
- The legacy PDM Web2 portal is not used. Every call goes to the Web API 2 REST surface (`api/<vault>/...`, `api/version/webapi`).
- No document custom property needs to change for write-back, since the three variables are written straight to the data card and need no property-to-variable mapping.
- No PDM task, and no automated drawing or PDF publishing, is part of this integration. Ingest reacts only to a file's workflow state and data card variables; producing or publishing drawings, PDFs or any other derived output is outside its scope.

## 13 reconciliation report

The two sync paths converge the catalogue towards the vault over time, but neither steps back to ask whether the catalogue as a whole still agrees with the vault and with itself. The reconciliation report is that check: a comparison pass, run on request, that never ingests anything. Quick mode reads only the database; deep mode additionally reads each linked file's `Glados.Ids` write-back variable from PDM. The report runs on the next scheduler tick, appears in the sync run log, and replaces the previous report.

Its findings fall into a few groups: CAD-owned rows that lost their PDM file, files stuck unresolved for longer than `stuck_after_days`, version, kind, part number and status drift between a file and its item, duplicate or orphaned part numbers, unmatched or missing documents, conflicts that a bought item could now resolve, and inconsistent status and successor pairs. The report dialog can re-check a file, which retries it.

Full rules: [reference/pdm-admin.md section 7](reference/pdm-admin.md#7-the-reconciliation-report).

## 14 catalogue preview

The made and bought catalogue views can show, to any logged-in user, which PDM files Glados has not fully caught up with yet, so a user sees what is coming without opening PDM. It is derived entirely from the snapshot table, never creates a row, and lists two buckets: files with no item at all (`unlinked`) and files whose vault version is ahead of their item (`newer`). It is unrelated to the admin "PDM files" list, and the preview button stays hidden while the integration is off.

Full rules: [reference/pdm-admin.md section 8](reference/pdm-admin.md#8-the-catalogue-preview).
