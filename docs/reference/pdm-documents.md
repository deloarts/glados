# pdm documents and thumbnails

The exact rules for which files a watched folder admits, how exported documents in a `documents` folder are attached to existing items, and how CAD thumbnails are fetched. The concept is in [PDM_INTEGRATION.md section 11](../PDM_INTEGRATION.md#11-documents-and-thumbnails). Both mechanisms live in `application/use_cases/pdm/pdm_documents.py` (`PdmDocumentSync`, `PdmThumbnails`) and run inside the same walk and refresh as ingest ([pdm-sync.md](pdm-sync.md)).

- [1 the file type rule](#1-the-file-type-rule)
- [2 the documents watched folder](#2-the-documents-watched-folder)
  - [2.1 released states](#21-released-states)
  - [2.2 matching by datacard or file name](#22-matching-by-datacard-or-file-name)
  - [2.3 picking the item](#23-picking-the-item)
- [3 categories](#3-categories)
- [4 storage and the document link](#4-storage-and-the-document-link)
- [5 replacement and missing files](#5-replacement-and-missing-files)
- [6 thumbnails](#6-thumbnails)
- [7 run entries](#7-run-entries)

## 1 the file type rule

- `made_item_extensions` (default `["sldprt"]`) and `bought_item_extensions` (default `["sldprt", "sldasm"]`) on `admin_pdm_settings` are lower-case extensions without a leading dot.
- A `made` or `bought` watched folder only snapshots a file whose extension is in the matching list.
- Any other file is not written to `pdm_file_snapshot_table` at all; it is only counted in the poll summary's `ignored_by_type` (`PollSummary.ignored_by_type`, `PollPdmVault._walk_children`) and so in the "N ignored by type" text of `last_poll_summary`.
- A `by_kind` folder does not know the kind at walk time, so it admits the union of both lists.
- Once a `by_kind` file's kind is resolved from the datacard, the file is re-checked against that kind's list, and a file that fails is `skipped` ("`<ext>` files are not `<kind>` items"), not `ignored_by_type`, since it was already snapshotted.
- `RefreshPdmFile` applies the same two checks, so an explicit folder's mismatch is never snapshotted and a `by_kind` folder's mismatch is rechecked once resolved; a trigger or a Retry for the wrong kind of file behaves exactly as the poller finding it.
- A `documents` folder is exempt from this rule.

## 2 the documents watched folder

- A watched folder of kind `documents` ("Exported Documents") is a vault folder a PDM task publishes drawings, DXF or STEP exports into.
- Every file under it is a document candidate, whatever its extension.
- Its files are never handed to `IngestPdmFile`; they are matched to an existing made or bought row and attached to it as one of that item's files.
- The snapshot `kind` of such a file is the string `"document"`, deliberately singular and distinct from the folder kind `"documents"`, so the made and bought conflict checks, which compare a snapshot's kind against its folder's, never fire for one.
- Ingest rule 1 plays no part for a document.

### 2.1 released states

- A document is synced only while its workflow state is one of `document_released_state_ids` (*Exported Documents → Released states* in the settings), one vault-wide list, since exports need not share the CAD files' workflow.
- A document in any other state, for example an export still being worked on, is `skipped` ("state not released for documents") before its datacard is read or anything is downloaded.
- A file attached earlier stays on its item when its document becomes unreleased.
- An empty list syncs no document at all.
- A save with the integration and a `documents` folder enabled but no such state is rejected.
- Changing the list requeues skipped files like any other sync scope change ([pdm-settings.md section 4.2](pdm-settings.md#42-what-a-save-requeues)).

### 2.2 matching by datacard or file name

- Every `documents` folder carries `match_by` (`PdmWatchedFolder.match_by`), either `"datacard"` or `"filename"`, which `UpdatePdmSettings` and `pdm_watched_folder.validate_watched_folder` require the moment `kind` is `"documents"`.
- `"datacard"` reads the file's mapped variables through the same `made_item_variable_map` and `bought_item_variable_map` ingest uses (`map_variables`), plus the same `Glados.Kind` variable a `by_kind` folder reads.
- With `"datacard"`, a made candidate needs both `part_number` and `revision` mapped and non-empty, and a bought candidate needs only `part_number`.
- `"filename"` extracts identity from the bare file name with `filename_pattern`, a regex with the named groups `part_number` and `revision` and an optional `kind` group.
- A pattern missing either required group, or one that does not compile, is rejected at save time.
- The regex is matched with `search`, not `fullmatch`, so it need not anchor to the whole name.
- A name the pattern does not match is `skipped` ("filename does not match the configured pattern").

### 2.3 picking the item

- An explicit kind, from the datacard's `Glados.Kind` or the regex's `kind` group, is tried on its own.
- With no explicit kind, made is tried first by `part_number` and `revision`, then bought by `part_number` alone; part numbers are unique app-wide, so both can never match.
- No match on either kind is `skipped` ("no matching item").
- No identity extracted at all (blank datacard variables, or a filename match with an empty group) is `skipped` ("identity variables missing").

## 3 categories

- A matched document's extension resolves an item file category through `document_categories` (default `{"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"}`), keyed by a lower-case extension without a leading dot.
- The map's values are validated on save against the union of `MadeItemFileCategory` and `BoughtItemFileCategory`.
- An extension absent from the map is `skipped` ("extension not mapped"), never an error.
- `document_excluded_kinds` maps an extension to the item kinds (`made`, `bought`) that do not receive it, so a bought item can go without its STEP export while made items keep theirs. The admin table shows it as one checkbox per kind on each category row, ticked by default.
- A document whose extension is excluded for the matched item's kind is `skipped` ("extension not ingested for bought items" or "... made items") after identity and category are resolved, and the reconciliation report treats that skip as deliberate.
- An exclusion never removes an attachment synced before it was set; that file stays on the item until someone deletes it, the same rule a document leaving its released state follows.
- Saving drops exclusions for extensions the category map no longer holds, and a changed exclusion requeues skipped files like any other sync scope change ([pdm-settings.md section 4.2](pdm-settings.md#42-what-a-save-requeues)).
- `BoughtItemFileCategory` has `DRAWING` and `DXF`, mirroring the made categories of the same name, so one map works for documents matched to either kind.
- The further value `image_and_thumbnail` (`domain.value_objects.pdm_document_category`) stores an exported image as the item's CAD rendering, an `ItemPicture` of source `cad_rendering`, not a file ([field-ownership.md section 2.7](field-ownership.md#27-itempicture)).
- `ItemPictureStore` decodes and re-encodes the image, so a file that only claims to be one is rejected, and derives the thumbnail from it at most 512 pixels on the longest side.
- A new version replaces only the CAD rendering, never a photo a person uploaded or the Data Portal picture.

## 4 storage and the document link

- The file is fetched with `GET files/{id}/{version}/download?folderId=`, a redirect the adapter follows (`HttpxPdmGateway.download_file`), capped at 64 MiB.
- It is stored through the same `UploadMadeItemFile` or `UploadBoughtItemFile` use case as a web or PAT upload, including its sha256 dedupe.
- The upload runs as the system user, so the web rule that only the newest revision is editable never blocks attaching an export to an older revision.
- `drawing`, `dxf` and `step` are singleton categories on both item kinds, which is what makes a new version replace the old file ([section 5](#5-replacement-and-missing-files)).
- The link between the vault file and the item file lives in `pdm_document_link_table` (`PdmDocumentLink`, `IPdmDocumentLinkRepository`), unique on `(vault_id, file_id)`, naming the kind, the item, the version last synced, and either `item_file_id` or, for an `image_and_thumbnail` document, `item_picture_id`.
- Every web item file response (`MadeItemFileResponse`, `BoughtItemFileResponse`) carries `from_pdm`, resolved from this table once per listing (`IPdmDocumentLinkRepository.get_linked_item_file_ids`), never per file.
- The PAT surface exposes no item file or picture routes.

## 5 replacement and missing files

- A document is re-synced only when its snapshot shows it changed (new, or a different version or workflow state id), the same diff the poller runs for made and bought files minus the kind and conflict checks, which do not apply to a `"document"` snapshot.
- Re-syncing a linked document repeats the upload, and since the target category is a singleton slot, the existing item file is replaced like any other singleton upload, with no special replace branch.
- A document that disappears from the vault, deleted or moved out of every watched folder, is swept into `missing` by the normal missing sweep, but only the snapshot row changes.
- The attached item file stays as it is, and the linked item's `pdm_sync_state` is untouched, since a missing export says nothing about whether the item's CAD data is current.

## 6 thumbnails

- Thumbnails are independent of the `documents` folder.
- After a successful, synced ingest of a made or bought file (`created`, `revised`, `updated`, `claimed` or `status`, the outcomes that mean `pdm_file_version` just changed), `PdmThumbnails.after_ingest` fetches the file's rendered thumbnail with `GET files/{id}/{version}/thumbnails?folderId=`, a redirect followed by `HttpxPdmGateway.download_thumbnail`, capped at 64 MiB.
- It stores the image as the item's CAD rendering, thumbnail only, through `ItemPictureStore`.
- It is skipped while an `image_and_thumbnail` document has supplied the CAD rendering, since that is the full-size export and the check-in thumbnail only a small preview.
- Bytes that do not decode as an image record a `thumbnail_error`.
- The picture is served by the item picture routes (`GET /{made|bought}-items/{id}/pictures/...`), web only.
- The fetch is gated by `thumbnails_enabled` on `admin_pdm_settings` (default off, `PUT /admin/settings/pdm`), because most vaults have nothing to fetch without PDM's Convert task configured to render a thumbnail on check-in, and an opt-in avoids a stream of `thumbnail_error` entries on such a vault.
- PDM reporting no thumbnail for a file, which happens even with the task configured, for example in a state the task does not run in, is a quiet no-op.
- Only a genuine transport or storage failure records a `thumbnail_error` entry.
- No vault permission beyond *Read file contents* on the states a watched file can be in is needed, for thumbnails and for the document download alike.

## 7 run entries

- A document sync records `document` or `document_error`.
- A thumbnail refresh records `thumbnail` or `thumbnail_error`.
- Both appear alongside the ingest and write-back actions in `GET /pdm/runs/{run_id}/entries`.
- The "PDM files" list's `kind` filter accepts `document` like any other value.
