# pdm settings

The rules behind every setting of the SolidWorks PDM integration: what each one does, its default, what a save validates and what a save changes. The concept and the overview of the settings are in [PDM_INTEGRATION.md section 3](../PDM_INTEGRATION.md#3-configuration); what the vault itself must provide, including the vault user's permissions, is in section 12 of the same guide.

- [1 the settings row and the gates](#1-the-settings-row-and-the-gates)
- [2 connection](#2-connection)
- [3 switching the integration on](#3-switching-the-integration-on)
- [4 datacard variable maps](#4-datacard-variable-maps)
  - [4.1 validation](#41-validation)
  - [4.2 what a save requeues](#42-what-a-save-requeues)
  - [4.3 the kind entry](#43-the-kind-entry)
  - [4.4 the field-mapping wire contract](#44-the-field-mapping-wire-contract)
- [5 watched folders](#5-watched-folders)
- [6 lifecycle state lists](#6-lifecycle-state-lists)
- [7 sync pacing](#7-sync-pacing)
- [8 other switches](#8-other-switches)
- [9 the external part-number pattern](#9-the-external-part-number-pattern)

## 1 the settings row and the gates

- Everything the integration needs lives on the singleton `admin_pdm_settings` row (`AdminPdmSettings`, `src/modules/external_data/domain/entities/admin_settings/pdm.py`), together with the last poll's status (`last_poll_at`, `last_poll_error`, `last_poll_summary`) and the cached Web API session ([pdm-sync.md section 1](pdm-sync.md#1-the-web-api-session)).
- `is_configured` is true once base URL, vault name, username and a stored password are all present.
- `is_pdm_enabled()` (`src/modules/external_data/application/services/pdm_integration.py`) takes the caller's already loaded settings and returns `settings.enabled and settings.is_configured`.
- Every other part of the integration checks `is_pdm_enabled()` before doing anything, since a vault switched on with no working connection would otherwise reserve a number space that nothing is actually watching.
- The settings are read with `GET /api/v1/web/admin/settings/pdm` (`read:settings`) and written with `PUT` on the same path (`write:settings`), which is what *Settings → SolidWorks PDM* calls.
- The links between PDM users and Glados users are not saved through this `PUT`; they go through `POST /admin/settings/pdm/users/link` ([pdm-ingest.md section 6](pdm-ingest.md#6-pdm-user-matching)).
- Settings that belong to one feature are stated with that feature: required fields in [pdm-ingest.md section 7](pdm-ingest.md#7-required-fields), the label fields and the feature-tree templates in [field-ownership.md section 7](field-ownership.md#7-label-properties-and-the-feature-tree-template), write-back in [pdm-writeback.md section 2](pdm-writeback.md#2-the-gate), and the document and thumbnail settings in [pdm-documents.md](pdm-documents.md).

## 2 connection

- The connection consists of base URL, vault name, service-account username and password, certificate verification and a timeout.
- The password is stored in plaintext, the same trust level as the SMTP password of the mail settings.
- "Test connection" (`VerifyPdmConnection`, `POST /pdm/test`) probes reachability and authentication with connection settings that have not been saved yet, so a bad configuration is caught before the integration is switched on.
- A blank password in the test means "use the stored password", so the admin need not retype it for every test.
- The test persists nothing, not even on success.

## 3 switching the integration on

- Switching `enabled` on is rejected with `PdmSettingsInvalidError` (400) unless the connection is fully configured, at least one watched folder is enabled, and at least one released state is configured for made or bought items.
- The released-state check uses the union of both kinds, so a deployment that watches only one kind need not configure the other kind's released states.
- With the integration and a `documents` folder enabled, a save without any `document_released_state_ids` is rejected ([pdm-documents.md section 2.1](pdm-documents.md#21-released-states)).

## 4 datacard variable maps

`made_item_variable_map` and `bought_item_variable_map` are separate dictionaries from field name to datacard variable name.

### 4.1 validation

- An empty string means unmapped, and ingest never touches an unmapped field.
- `UpdatePdmSettings` rejects an unknown field name.
- `UpdatePdmSettings` rejects a variable name used for two fields of the same map.
- `UpdatePdmSettings` rejects a map that maps any field other than `part_number`, `revision` and `kind` without mapping both `part_number` and `revision`, since ingest would have no identity to key on.
- `item_field_ownership.item_fields()` is the single source of truth for which fields each map may name; [field-ownership.md](field-ownership.md) has the per-field tables.

### 4.2 what a save requeues

- Saving a change to the maps, the state lists (including `document_released_state_ids`) or the watched folders requeues every `skipped` snapshot to `pending`, because a skip for a settings reason only clears once that setting changes.
- The same save first marks every snapshot whose stored path no longer falls under an enabled watched folder as `missing`, and its linked made or bought item too, which is the outcome the trigger path gives a file that moved outside every watched folder.
- The missing marking comes first because the poller never walks such a file again, so a requeued row there would stay `pending` forever.
- A stored path that is merely stale after a folder rename in PDM heals on the next poll, which treats a `missing` file it finds again as changed.

### 4.3 the kind entry

- `kind` is a mappable field with the default variable name `Glados.Kind`, but it is not a column on either item.
- It decides which catalogue a file found under a `by_kind` watched folder belongs to, once the file's datacard variables have been read.
- It backstops an explicit `made` or `bought` folder against a file whose kind variable disagrees with the folder ([pdm-sync.md section 3.8](pdm-sync.md#38-kind-conflicts-and-skips)).
- Whenever either map sets `kind`, both maps must name the same non-empty variable.
- At runtime only the made map's entry is read (`pdm_variables.kind_variable_name`).

### 4.4 the field-mapping wire contract

- `GET /pat/settings/field-mapping` serves the effective mapping to the SolidWorks add-in.
- Its field set and order are a fixed wire contract: fields added later (`kind`, the write-back fields, the labels, the feature-tree field, the made item's customer fields and the bought item's `edp_part_id`) are appended at the end, never inserted.
- How the label fields, the feature-tree field and its templates appear on the wire is in [field-ownership.md section 7](field-ownership.md#7-label-properties-and-the-feature-tree-template).

## 5 watched folders

- Each entry (`PdmWatchedFolder`) is one vault folder the poller scans and carries `path`, `kind`, `recursive`, `enabled` and `folder_id`, plus `match_by` and `filename_pattern` for a `documents` folder.
- Folders are picked through the folder browser (`GET /admin/settings/pdm/folders`, `BrowsePdmFolders`), which returns each folder's PDM id alongside its name and path.
- `kind` is `made`, `bought`, `by_kind` or `documents` ([pdm-documents.md section 2](pdm-documents.md#2-the-documents-watched-folder)), and a newly added folder in the settings UI defaults to `by_kind`.
- `recursive` includes subfolders, and `enabled` lets an admin pause a folder without losing its configuration.
- `path` is the field shown in the UI and the one checked for uniqueness.
- `folder_id` is set whenever the picker resolved one and is optional, so a hand-typed entry, or one saved without it, round-trips as `None`.
- `folder_id` is the fallback the walk follows when `path` no longer resolves, as after a rename in PDM; every run resolves `path` first and records an error entry whenever the two disagree ([pdm-sync.md section 3.7](pdm-sync.md#37-moves-and-renames)).
- The missing-file sweep attributes snapshots by the folder ids actually walked, never by path.

## 6 lifecycle state lists

- `made_released_state_ids`, `made_obsolete_state_ids`, `made_replaced_state_ids`, `bought_released_state_ids`, `bought_obsolete_state_ids` and `bought_replaced_state_ids` are PDM workflow state ids chosen from `GET /admin/settings/pdm/workflows` (`GetPdmWorkflows`).
- They drive the lifecycle mapping onto `status` ([pdm-ingest.md section 2.1](pdm-ingest.md#21-rule-1-state)), and each kind is watched against its own triple, since the two catalogues need not share a workflow.
- `AdminPdmSettings.released_state_ids_for(kind)`, `obsolete_state_ids_for(kind)` and `replaced_state_ids_for(kind)` resolve the list for a file's kind; a check without a kind uses the union of all kinds' lists rather than picking one arbitrarily.
- The three lists of one kind must be pairwise disjoint, so a workflow state drives at most one lifecycle status; this is checked independently for made and for bought (`AdminPdmSettings.assert_state_id_lists_disjoint`, enforced by `UpdatePdmSettings`, 400 `PdmSettingsInvalidError` on overlap).
- `document_released_state_ids` is a seventh, separate list for `documents` folders; it drives no status and is not checked against the other six.

## 7 sync pacing

- `poll_interval_minutes` paces `RunPdmPollIfDue`; new installs default to 15 minutes, the column's server default.
- `cold_folder_max_multiplier` caps the cold-folder backoff at `poll_interval_minutes` times this value ([pdm-sync.md section 3.10](pdm-sync.md#310-cold-folder-cadence)); it defaults to 8 and is editable from 1 to 64, where 1 disables backoff because every folder then stays at the base interval.
- `ingest_concurrency` is how many changed files a poll run ingests at once ([pdm-sync.md section 3.4](pdm-sync.md#34-parallel-ingest)); it defaults to 4 and is editable from 1 to 16, where 1 ingests one file after another.
- More concurrency is faster, but every parallel ingest is another stream of Web API calls against the PDM server.

## 8 other switches

- `cad_items_read_only` decides whether a CAD-owned row's PDM-owned fields are actually enforced read-only in the web and PAT; it defaults to `true` for new installs, the safer starting posture ([field-ownership.md section 6](field-ownership.md#6-enforcement)).
- `stuck_after_days` is how many days a snapshot may sit unresolved before the reconciliation report's `stuck_file` category flags it; it defaults to 7 and is editable from 1 to 365.
- `set_approver_from_pdm` is off by default; when on, ingest sets `approver_id` to the resolved releaser alongside the changelog attribution, and when off ingest never touches `approver_id` ([pdm-ingest.md section 5](pdm-ingest.md#5-pdm-releaser-attribution)).
- `addin_language` is the language the pat surface gives article group, source item type, fabrication method and inspection method names in, and with that the language the add-in writes `article_group_names` and `process_names` into the datacards ([field-ownership.md section 7](field-ownership.md#7-label-properties-and-the-feature-tree-template)). Empty, the default, means the tenant's default language, and so does a code no longer offered. A change reaches a datacard the next time the add-in writes that file; the pat lookups ETag includes the language, so the add-in's cache refreshes.

## 9 the external part-number pattern

- The pattern is not stored on `admin_pdm_settings`; it lives on the *Numbering* settings as `AdminMadeItemSettings.pdm_part_number_pattern` and `AdminOrderSettings.pdm_part_number_pattern`, one regex per kind.
- While the integration is enabled, a hand-typed number in the web, PAT or batch paths must not match the pattern, because those numbers are reserved for PDM.
- A part number delivered by PDM must fully match the pattern for ingest rule 4 to accept it, and an empty pattern skips every file of that kind ([pdm-ingest.md section 2.4](pdm-ingest.md#24-rule-4-pattern)).
- Saving the numbering settings is rejected when an internal format's rendered example matches the external pattern ([field-ownership.md section 1.1](field-ownership.md#11-ownership-by-part-number-scheme)).
