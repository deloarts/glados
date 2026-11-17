# pdm write-back

The exact behaviour of `PdmWriteBack`, the one opt-in path that writes to the PDM vault. The concept and the PDM-side checklist are in [PDM_INTEGRATION.md section 10](../PDM_INTEGRATION.md#10-write-back-to-pdm).

- [1 what is written](#1-what-is-written)
- [2 the gate](#2-the-gate)
- [3 when it runs](#3-when-it-runs)
- [4 mechanics](#4-mechanics)
- [5 errors](#5-errors)
- [6 sync log](#6-sync-log)

## 1 what is written

- `PdmWriteBack` (`src/modules/external_data/application/services/pdm_writeback.py`) writes exactly three version-free datacard variables onto a linked file's card after every ingest attempt.
- `Glados.Ids` is a single-line JSON array of `{"revision", "public_id", "pdm_version"}` for every non-deleted Glados row of the family: every made revision, newest first, or the one bought row with `revision` always `null`.
- `Glados.NewestRevisionSyncState` is `synced` for a `created`, `revised`, `updated`, `claimed` or `status` outcome, and otherwise `conflict: <reason>` or `skipped: <reason>`, the reason being the message `IngestOutcome` already carries.
- `Glados.NewestRevisionSyncedAt` is an ISO 8601 UTC timestamp.
- Write-back never transitions a file's workflow state and never writes any other variable.

## 2 the gate

- Write-back is off by default (`writeback_enabled` on `admin_pdm_settings`, set through `PUT /admin/settings/pdm` with `write:settings`).
- Turning it on requires all three fields (`glados_ids`, `newest_revision_sync_state`, `newest_revision_synced_at`) to be mapped to a non-empty variable name in both `made_item_variable_map` and `bought_item_variable_map`, and to the same name in both.
- The same-name rule exists because `PdmWriteBack` reads the map of the file's own kind, so a mismatch would silently write a different variable depending on the kind.
- The three fields are server-owned and write-only: `map_variables()` in `pdm_variables.py` excludes them the same way it excludes `kind`, so no ingest rule reads them back, and the SolidWorks add-in never writes them.
- The default variable names (`_MADE_ITEM_VARIABLE_MAP_DEFAULT` and `_BOUGHT_ITEM_VARIABLE_MAP_DEFAULT` in `src/modules/external_data/adapters/outbound/persistence/models/admin_settings_model/pdm.py`) are `Glados.Ids`, `Glados.NewestRevisionSyncState` and `Glados.NewestRevisionSyncedAt`.
- The stored maps are read as complete. A map that `PUT /admin/settings/pdm` sends must name every mappable field, with an empty name for an unmapped one, and a field added to the maps later gets its default in every stored row through a data migration ([development-migrations.md section 3.3](development-migrations.md#33-data-steps)).

## 3 when it runs

- `PdmWriteBack.after_outcome(vault_id, file, kind, outcome, run)` runs once per touched, linked file, right after the ingest transaction that produced `outcome` has committed.
- `PollPdmVault._ingest_one` calls it after a normal ingest and after the private-state skip of an already linked file, which also covers `_retry_conflicts`, since that delegates to `_ingest_one`.
- `RefreshPdmFile` calls it in the same two places.
- It is a no-op unless `writeback_enabled` is set and `outcome.item_id` is not `None`, because an outcome with no item (identity variables missing, a brand-new conflict with nothing parked) has no id list to write.

## 4 mechanics

- `GET files/{fileId}/{version}/datacard?folderId=` fetches the full datacard: every configuration's variable definitions including `VarId`, `VarType` and `VersionFree`, which is richer than the `variables` endpoint ingest reads and the only way to learn a variable's id.
- All three target variables must be present under the "@" file-level configuration and marked `VersionFree`, the same configuration rule as ingest's `select_configuration`.
- Every SolidWorks file carries an "@" configuration, so a card without one is never read from a fallback first configuration; it records one `writeback_error` run entry with the message "no file-level datacard configuration".
- If the "@" configuration exists but a variable is missing or not version-free, nothing is written and one `writeback_error` entry names the variables and the reason.
- Otherwise `POST files/{fileId}/datacard?folderId=` writes just those three variables, never the whole card, to that one configuration.
- When any of the three variables' ids appears in the datacard's `VariablesWithWriteAllConfigs` list (PDM's "update all versions" flag, set per variable in the PDM admin tool), the write goes to every configuration the datacard returned instead.
- A successful write records one `writeback` run entry.

## 5 errors

- Every PDM error inside `after_outcome` (a missing or non-version-free variable, a transport failure, a non-2xx response) is caught and recorded as `writeback_error`.
- Nothing write-back raises can fail the ingest it follows, abort a poll run or change `IngestOutcome`.
- A failed write-back is retried the next time the same file is touched (the next poll tick that finds it changed, or the next trigger), since `after_outcome` always recomputes and rewrites the full state instead of diffing against what PDM holds.

## 6 sync log

- The poll summary's one-line text includes "N written back", tallied in memory during the run (`PollSummary.written_back`) because the run entries are not read back for counting.
- The per-file entries in `GET /pdm/runs/{run_id}/entries` carry the two write-back actions `writeback` and `writeback_error` alongside the ingest actions.
