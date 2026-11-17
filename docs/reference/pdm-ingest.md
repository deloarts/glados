# pdm ingest

The rules `IngestPdmFile` applies to one PDM file, the required-field check it shares with pre-release validation, and the dry run itself. The concept is in [PDM_INTEGRATION.md section 5](../PDM_INTEGRATION.md#5-ingest-rules); [field-ownership.md](field-ownership.md) is the field-by-field source of truth these rules implement, and its per-field tables are not repeated here.

- [1 the ingest contract](#1-the-ingest-contract)
- [2 the rules](#2-the-rules)
  - [2.1 rule 1, state](#21-rule-1-state)
  - [2.2 rule 2, identity](#22-rule-2-identity)
  - [2.3 rule 3, kind-changed guard](#23-rule-3-kind-changed-guard)
  - [2.4 rule 4, pattern](#24-rule-4-pattern)
  - [2.5 rule 5, coercions](#25-rule-5-coercions)
  - [2.6 rule 6, version guard](#26-rule-6-version-guard)
  - [2.7 rule 7, obsolete and replaced states](#27-rule-7-obsolete-and-replaced-states)
  - [2.8 rule 8, made items](#28-rule-8-made-items)
  - [2.9 rule 9, bought items](#29-rule-9-bought-items)
  - [2.10 rule 10, what every success writes](#210-rule-10-what-every-success-writes)
  - [2.11 rule 11, events](#211-rule-11-events)
- [3 the single transaction](#3-the-single-transaction)
- [4 renumbering](#4-renumbering)
- [5 pdm releaser attribution](#5-pdm-releaser-attribution)
- [6 pdm user matching](#6-pdm-user-matching)
- [7 required fields](#7-required-fields)
- [8 pre-release validation](#8-pre-release-validation)
  - [8.1 what the dry run checks](#81-what-the-dry-run-checks)
  - [8.2 the api-key surface](#82-the-api-key-surface)
  - [8.3 the pat surface](#83-the-pat-surface)
  - [8.4 reasons and pending fields](#84-reasons-and-pending-fields)
  - [8.5 the predicted action](#85-the-predicted-action)

## 1 the ingest contract

- `IngestPdmFile` lives in `src/modules/external_data/application/use_cases/pdm/ingest_pdm_file.py`, with the made path in `_ingest_made.py`, the bought path in `_ingest_bought.py` and their shared outcome steps in `_ingest_outcome.py`.
- The poller and the trigger worker are its only callers: they read the file's variables from the Web API, pick a configuration (`pdm_variables.select_configuration`) and hand in a `PdmFilePayload`, so ingest never talks to the gateway for the file itself.
- Ingest always resolves and acts as the system user (`SYSTEM_USER`, seeded by `InitDatabase`), which exempts it from ownership enforcement ([field-ownership.md section 6](field-ownership.md#6-enforcement)).
- A business condition never raises: a mismatched pattern, an unwatched state, a stale version, an unresolved reference or a part-number clash all come back as a normal `skipped` or `conflict` outcome, so a poll run keeps going through its other files.
- Only a genuine programming or transport error propagates, and the caller records it against the file without touching anything the ingest committed.
- The rules run in the fixed order below, and the code comments in `ingest_pdm_file.py` and its `_ingest_*.py` collaborators refer to these rule numbers.

## 2 the rules

### 2.1 rule 1, state

- The payload's workflow state id decides the linked row's target `status`: `released_state_ids_for(kind)` gives `active`, `obsolete_state_ids_for(kind)` gives `inactive`, and `replaced_state_ids_for(kind)` gives `replaced`.
- Made and bought items are checked against their own triple of lists.
- Any other state is `skipped` ("state not watched").
- State is checked first because a file still being worked on usually has no PDM revision yet and would otherwise be reported as an identity problem.
- Whenever the resulting status is `active` or `inactive`, a `successor_item_id` already on the row is cleared with its own changelog line ("successor cleared by PDM state ...").
- A `replaced` target never touches the successor, because PDM carries no successor reference of its own and the successor stays a web decision ([field-ownership.md section 4](field-ownership.md#4-lifecycle-mapping)).

### 2.2 rule 2, identity

- `part_number` must resolve to a non-empty value once the variable map is applied.
- `revision` must too, always for a made item, and for a bought item only when the admin's required-field selection names it, which it does by default ([section 7](#7-required-fields)).
- Otherwise the file is `skipped` ("identity variables missing").

### 2.3 rule 3, kind-changed guard

- If `(vault_id, file_id)` is already linked under the other catalogue, the file is parked as a `conflict` naming that other kind.
- Made and bought items key their PDM link the same way, so one file can never legitimately be linked under both.

### 2.4 rule 4, pattern

- `part_number` must fully match the kind's external pattern from the *Numbering* settings ([pdm-settings.md section 9](pdm-settings.md#9-the-external-part-number-pattern)).
- No pattern configured, or no match, is a `skip`, not a `conflict`.

### 2.5 rule 5, coercions

- `pdm_variables.py` turns each raw datacard string into the typed value a field needs and never raises.
- `parse_mass` accepts a comma or dot decimal separator and rounds half away from zero, matching the add-in's own rounding.
- `parse_date` accepts ISO or German (`DD.MM.YYYY`) text.
- `parse_int_list` drops an unparsable token individually rather than failing the whole list, and an id that does not match a real article group is dropped with a warning folded into the outcome message.
- `parse_int` resolves a single reference id.
- `parse_edp_part_id` reads an EPLAN Data Portal part id, where a blank, unparsable or non-positive value means no part.
- `parse_processes` reads the `Glados.Processes` JSON array the add-in writes and drops one malformed step rather than the whole routing.

### 2.6 rule 6, version guard

- A payload for an already linked row is not applied when the row is at a newer file version, or at the same version with the status the payload's workflow state maps to; the outcome is `skipped` ("already at version N").
- The same version at a different status still goes through, because a workflow transition does not necessarily create a new file version.
- The snapshot keeps its link in every case.
- At the same version the file is in sync, so the snapshot reads `ingested` and the item's `pdm_sync_state` returns to `synced`; this is how a forced poll settles a linked file that reappeared after being marked `missing`.
- A payload behind the stored version stays `skipped`.
- The outcome names no item, since nothing was written to one, so write-back and the thumbnail fetch leave the vault alone.
- The guard makes a redelivered or out-of-order event and a manual poll harmless, and makes the conflict retry safe to run unconditionally.

### 2.7 rule 7, obsolete and replaced states

- A target status of `inactive` or `replaced` with no existing item is `skipped` ("obsolete state without a matching item" or "replaced state without a matching item").
- With an existing item, only the status flips, the transition is recorded naming the old and new status, and no other field changes.
- The successor rule of [rule 1](#21-rule-1-state) applies here too.

### 2.8 rule 8, made items

- No existing row for the file creates one through `CreateMadeItem`, the same use case the web and PAT paths use.
- An existing row whose `PDM.Revision` differs from the newest Glados revision creates the next revision through `CreateMadeItemRevision`, with the predecessor status taken from the PDM predecessor setting.
- When the predecessor already carried a different successor than the new revision, because a human set one earlier, the override is recorded with its own changelog line.
- Both the create and the revise path first check required fields and `skip` without writing anything if one is missing ([section 7](#7-required-fields)).
- An existing row at the same revision is updated in place and never checked against required fields.
- An in-place update overwrites only fields flagged "PDM: update in place" in the revision policy, and only when they are mapped and actually different.
- `source_item_id` follows its own dual-owned shadow rule regardless of that flag, so the CAD value wins only when it moved since the last sync.
- `processes` is a whole-routing replace, gated by its own policy flag.
- Because the target status here is always `active`, this path also reactivates a row left `inactive` or `replaced` without a revision bump and clears a stale successor, as rule 1 does on the status-flip path.

### 2.9 rule 9, bought items

- An existing row for the file is updated in place and never checked against required fields; every mapped field is overwritten unconditionally, since bought items have no per-field policy.
- With no existing row, a live row that already carries the incoming part number is claimed directly, ahead of any gtin or order-code match, because part numbers are unique app-wide and never reused; the part-number registry is not touched, since the number is already registered to that row.
- A row whose part number is already linked to a different PDM file is a `conflict` ("part number linked to another PDM file (id N)"); it can never be the file being ingested, since that row would already have been found as the existing linked row.
- Failing a part-number match, an exact match among unclaimed items (`gtin`, or `manufacturer_id` plus `order_code_1`) is claimed: `data_source` flips to `CAD`, the part number is replaced by PDM's (the old number released from the registry if now unused), and a changelog line records the file and the number of fields overwritten.
- With no match at all, a new row is created.
- All three paths (part-number claim, gtin or order-code claim, create) first check required fields and `skip` if one is missing.
- A resolved `manufacturer_id` is separately required to reach any of the three paths, and an unresolved value is a `conflict` there, while an in-place update simply leaves the field untouched.
- Because the target status here is always `active`, the in-place update and the claim path also reactivate a row left `inactive` or `replaced` and clear a stale successor.
- All three writes apply `edp_part_id` under its dual-owned shadow rule (`pdm_edp_part_id`), so the CAD value wins only when it moved since the last sync.
- A changed `edp_part_id` writes its own changelog line and requests the item's Data Portal picture in the same transaction ([eplan-data-portal.md section 4.5](../EPLAN_DATA_PORTAL_INTEGRATION.md)); the part id is never checked against the portal here.

### 2.10 rule 10, what every success writes

- Every successful write sets the item's `vault_id`, `pdm_file_id`, `pdm_file_version`, `pdm_synced_at` and `pdm_sync_state = synced`.
- It writes the file's snapshot row with its `sync_state`, `part_number`, `revision` and `item_id`, and a changelog line naming the file and what happened.
- Every rule, including a plain skip, ends by updating the snapshot row, so the admin "PDM files" list always explains a file's current state.

### 2.11 rule 11, events

- `PdmFileIngested` (`vault_id`, `file_id`, `kind`, `item_id`, `action`, `part_number`, `revision`) publishes on every successful write, with `action` one of `created`, `revised`, `updated`, `status` or `claimed`.
- `PdmIngestConflict` (`vault_id`, `file_id`, `kind`, `part_number`, `reason`) publishes whenever a write is parked instead.
- Both key on `(vault_id, file_id)` rather than only the Glados item id, since a conflict may never resolve to an item.

## 3 the single transaction

- Every write goes through one transaction, including the three brand-new-row actions (made create, made revise, bought create).
- Those three reuse `CreateMadeItem`, `CreateMadeItemRevision` and `CreateBoughtItem`, each of which splits its execute into a non-committing half (every pre-check, ending in a `write` closure) and the commit itself.
- `IngestPdmFile` calls the non-committing half and folds the returned closure into its own write, alongside the PDM link columns, the changelog line and the snapshot row.
- It commits exactly once per ingested file through `retry_on_conflict.commit_with_number_retry`, and `IPdmFileSnapshotRepository.upsert_many` never commits on its own for exactly this caller.
- A crash mid-ingest therefore leaves either nothing or a fully linked row, the same guarantee the in-place update, the obsolete-state transition and the bought claim and update give.
- Two files that carry the same new part number and are ingested at once, by two poll workers or by a poll and the trigger worker, both pass the checks before the write. The second one's registry claim waits for the first's transaction and then fails on the registry's key, and `commit_with_number_retry` rolls it back without a retry. `IngestPdmFile.execute` then decides the file once more against what the first one committed, so the second file gets the outcome the next poll would give it, a `conflict` with the item the first file created, and nothing else of its write remains. Should that second decision lose a race as well, the file is parked as a `conflict` ("part number N was written by a concurrent ingest"), so a race never escapes as an exception. `tests/pg/test_pdm_ingest_number_races.py` holds this on Postgres.

## 4 renumbering

- PDM owns a linked row's part number.
- Before the version guard, ingest compares the linked row (for a made item, the whole family linked to the file) with the part number the file carries now.
- When they differ, every linked row takes PDM's number in its own committed step: the new number is claimed in the part-number registry, the old one stays registered because part numbers are never reused, and each row gets a changelog line ("Part number changed by PDM from X to Y.").
- A file that is otherwise in sync reports this as an `updated` outcome, so the run log and write-back see the change; any other outcome carries the note in front of its own message.
- When the new number already belongs to another item, the file is parked as a `conflict` naming that item, and nothing is renumbered ([field-ownership.md section 5](field-ownership.md#5-conflicts-and-parked-events)).

## 5 pdm releaser attribution

- On a `created`, `revised`, `claimed` or `status` outcome, `IngestPdmFile` reads the ingested version's workflow transitions (`GET .../files/{fileId}/transitions`).
- It picks the newest transition landing in the target state list: the released list for created, revised and claimed, and the obsolete or replaced list matching the target status for the status flip.
- No datacard variable carries this; it comes from the vault's transition history.
- The transition's PDM user is resolved to a Glados user by `application.services.pdm_users.resolve_pdm_user`: an explicit `UserPdmLink` row first, then a case-insensitive username match.
- A resolved releaser replaces the system actor's name on the changelog line and becomes `changed_by_id` on made items; bought items carry no such column.
- An unresolved releaser still gets its raw PDM username into the changelog text, and all other attribution stays at the system-actor default.
- `revision_date` and `revision_note` (made items only) fall back to the matching transition's date and comment when the datacard leaves the field unmapped or blank.
- With `set_approver_from_pdm` on, ingest also sets `approver_id` to the resolved releaser on made and bought items alike; it is left untouched when the toggle is off or the releaser does not resolve.
- A transitions read failure (session, connectivity, an unreachable vault) never fails the ingest: it is logged at warning, folded into the outcome's message, and the write proceeds as it would with no attribution.
- In-place updates never read transitions, since a field already on the row settled its attribution when it was written.

## 6 pdm user matching

- `GET /admin/settings/pdm/users` (`ListPdmUsers`) lists every vault user (`GET api/{vaultName}/users`) with its existing link, a `user_pdm_link_table` row, or, for an unlinked user, a same-identity guess.
- The guess is a case-insensitive username match first, and only when that fails, one more Web API call (`GET .../{userId}/Extended`) to try an email match.
- The configured service account is flagged and never proposed or linkable.
- Several vault users may link to, or be proposed for, the same Glados user, because one person can release under more than one PDM account; `user_pdm_link_table.pdm_user_id` is the only column with a uniqueness constraint.
- `POST /admin/settings/pdm/users/link` (`LinkPdmUsers`) saves the admin-confirmed links from the "Match PDM Users" dialog, and a `user_id` of `null` unlinks.
- Both routes require `write:settings`; the list route needs it rather than `read:settings` because the dialog is reached only from the writable settings tab.
- Relinking a PDM user id already held by a different Glados user moves the link rather than failing the batch, since the admin's action in the dialog is the more recent intent.

## 7 required fields

- The locked set lives in code (`src/modules/external_data/domain/services/pdm_required_fields.py`), never appears in the admin's selection and is always enforced: `part_number` and `article_name` for both kinds, plus `order_code_1` and `manufacturer_id` for bought items and `revision` for made items.
- `article_name` and `order_code_1` never fall back to the PDM file's name; a file that leaves either unmapped or blank is `skipped`.
- `revision` is locked only for made items, where `(part_number, revision)` keys the row; a bought item is keyed by `part_number` alone, so for bought items `revision` is a configurable required field, on by default.
- With the bought `revision` requirement off and the revision variable blank, ingest still creates or claims the bought item with `revision` left `null`, like a `WEB`-created bought item.
- On top of the locked set, an admin can mark any other mappable field required, plus the made pseudo-rule `fabrication_step`, which is satisfied once the parsed `Glados.Processes` array has at least one entry with role fabrication and a non-null fabrication method id.
- The selection is stored as `AdminPdmSettings.required_fields`, shaped `{"made": [...], "bought": [...]}`, and defaults to `material` and `fabrication_step` for made items and `revision` for bought items.
- Saving the settings drops a locked or duplicate name silently and rejects an unrecognised one.
- The settings response also serves `locked_required_fields` and `required_field_rules`, both read-only, so the settings page renders the full checklist without hardcoding either list.
- Label fields and the feature-tree field are never required-field candidates (`pdm_required_fields.required_field_candidates()` excludes `addin_written_fields()`).
- `application.services.pdm_required_fields.missing_required_fields` evaluates the locked set and the selection together against one file's mapped values and parsed processes.
- A field counts as present once its mapped value is non-empty after stripping.
- A configured field with no PDM variable mapped at all is reported as "`<field>` (no PDM variable mapped)" rather than as blank, since ingest could never populate it.
- The same evaluator backs `ValidatePdmPayload` and the create, revise and claim paths of `IngestPdmFile`, which `skip` with the message `required fields missing: <field>, <field>, ...` before any write or registry claim.
- An in-place update or a status flip is never checked, because a field already on the row does not become un-required by staying unchanged.
- `IngestPdmFile` runs after release, when every required field is expected to be present, so it appends the evaluator's output to its skip message unfiltered.
- `ValidatePdmPayload` runs before release and first passes the output through `split_missing_required_fields` in the same module, which separates the reasons the engineer still owns (appended to `reasons` whenever the prediction is `created`, `revised`, `claimed` or `unknown`) from the PDM-owned field names still pending (added to `pending_pdm`, [section 8.4](#84-reasons-and-pending-fields)).

## 8 pre-release validation

### 8.1 what the dry run checks

- `ValidatePdmPayload` (`src/modules/external_data/application/use_cases/pdm/validate_pdm_payload.py`) is a read-only dry run of `IngestPdmFile`'s rules against already mapped datacard values.
- It checks the identity variables, the external part-number pattern, a file already linked under the other kind, the part-number registry, the manufacturer, bought-item, source-item and article-group references, the form of a bought item's Data Portal part id (never asking the portal), and the file-extension rule.
- It never writes anything and never fires an event.
- Unlike a real ingest it evaluates every applicable rule instead of stopping at the first failure.
- It never looks at `pdm_file_version`, so there is no version guard, because validation is about the values and not about whether they are newer than what is linked.
- It always simulates a released (active) target regardless of the file's current workflow state, since the question is whether the file would ingest cleanly once released.
- The result names the `kind`, the identity, every `reason`, the PDM-owned fields still pending in `pending_pdm`, and `would`, using the action vocabulary of `IngestOutcome` (`created`, `revised`, `updated`, `claimed`, `unknown`).
- Both surfaces answer `409` while the integration is off or unconfigured, since there is nothing to validate against.
- Glados never blocks a PDM state transition itself; acting on a result with `ok: false` is left to the caller. The vault add-in never validates, since PDM transition conditions guard releases.
- The SolidWorks add-in shows the verdict as a status line next to its sync indicator and never blocks a save on an unreachable Glados; it only reports that the check could not run.

### 8.2 the api-key surface

- `POST {API_KEY}/pdm/files/{file_id}/validate` (`use:pdm_addin`, `src/modules/external_data/adapters/inbound/api/v1/key/endpoints/pdm.py`) serves a caller that checks a file in the vault before a release, such as a script or a vault hook; the vault add-in does not call it.
- `ValidatePdmFile` (`src/modules/external_data/application/use_cases/pdm/validate_pdm_file.py`) resolves the file fresh from the Web API by id, as `RefreshPdmFile` does, never trusting anything the caller could not already read.
- It matches the file to a watched folder, resolves its kind from the folder or, for a `by_kind` folder, from the datacard, and hands the result to `ValidatePdmPayload`.
- A file outside every watched folder or inside a `documents` folder comes back as a normal `200` with `kind: null` and an explanatory reason.
- Only a file PDM cannot resolve at all, or cannot read (private state or a missing grant), is a `404`.
- `POST {API_KEY}/pdm/files/validate/batch` runs the same check for 1 to 50 `file_ids` (`ValidatePdmFile.execute_batch`), resolving them with one Web API read and validating them one by one until 12 seconds have passed.
- Each distinct id comes back in request order with its own `outcome`: `validated` (with the `validation` result), `not_found` (the single route's `404`), `failed` (a Web API error reading it) or `not_validated` (the time budget was spent).
- Only a validated result with `ok: false` is meant to stop a release, and a caller checking a transition validates all its files with one call to the batch route.
- This surface reports `file_identity` as `"not_applicable"`, since it never needs to resolve a file.

### 8.3 the pat surface

- `POST /api/v1/pat/pdm/validate` uses standard PAT auth with no extra permission, the same posture as `GET /pat/settings/field-mapping`, and is built for the SolidWorks add-in's check button right after it writes the `Glados.*` custom properties.
- The body carries `kind` (or `null` to resolve it from the `Glados.Kind` property like a `by_kind` folder), an optional `file_name` for the extension rule, an optional `file_path` (the document's full local path, for example `C:\DEMO-VAULT\Engineering\Glados\CAD-1001.sldprt`), and `variables`, the document's property values keyed by the names the field maps use.
- There is no vault round trip and no vault file id, so when `file_path` is given, `ValidatePdmPayload` resolves a file itself against the snapshot table (`IPdmFileSnapshotRepository.find_by_path_suffix`).
- The resolution is a case-insensitive match of a snapshot's vault-relative path as a suffix of the full document path, preferring the longest match and giving up when two or more rows tie; only rows whose lower-cased file name equals the document's are compared, a narrowing done in SQL on an index.
- Existing rows are always matched by part number first, which keeps the endpoint usable without `file_path` or a resolvable match.
- The response's `file_identity` is `"resolved"` or `"unresolved"`.
- Without a resolved identity, the check for a file already linked under the other kind is skipped, and a part number already linked to a PDM file is reported as an in-place update rather than a guessed link to a different file, with a note in the response's `notes` list.

### 8.4 reasons and pending fields

- Both surfaces run before release, when every PDM-owned field (`part_number` and `revision` today, plus any other PDM-owned field an admin marked required) is still blank, because the release workflow assigns it.
- A missing PDM-owned field is therefore never a `reasons` entry and never makes `ok` false; it is named in `pending_pdm`, a list of bare field names in the order the admin "Item Fields" tab lists them, meaning "expected empty before release, assigned by the workflow".
- `reasons` keeps every requirement the engineer still owns: a missing add-in-owned or web-owned required field, the `fabrication_step` pseudo-rule, a dangling reference, an unresolved kind, a wrong extension, a duplicate part-number claim and the like.
- `ok` follows from `reasons` alone.
- A `required fields missing: ...` reason lists only the non-PDM-owned fields still missing, and is omitted when only PDM-owned fields are missing.

### 8.5 the predicted action

`would` is predicted as if every `pending_pdm` field had already been assigned by the workflow.

| Situation | `would` |
| --- | --- |
| No part number yet, made or bought. | `created` |
| Made, part number known, family exists in Glados, revision still pending. | `revised` |
| Made, part number known, no family in Glados yet. | `created` |
| Made, part number and revision known and matching the newest revision on file. | `updated` |
| Bought, part number known; a pending revision never changes this row, since revision is not part of a bought item's identity. | The normal outcome: `updated` if a live row carries the part number, `claimed` if an unlinked row matches by gtin or manufacturer and order code, `created` otherwise. |

- `would` is `unknown` only for a genuinely undecidable case: the kind unresolved, a file outside every watched folder or in a `documents` folder (API-key surface), or a bought part number already linked to a different PDM file.
- A pending PDM-owned field alone never makes `would` `unknown`.
