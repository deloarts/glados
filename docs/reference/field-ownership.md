# field ownership

The authoritative domain rules for which system owns which field of a made or bought item while the SolidWorks PDM integration is enabled, what happens when a value changes, and how the rules are enforced. The concept, the seven principles in short and the legend of the editor and *Rev* columns are in [FIELD_OWNERSHIP.md](../FIELD_OWNERSHIP.md); the machinery that applies these rules is in [pdm-ingest.md](pdm-ingest.md).

- [1 principles in full](#1-principles-in-full)
  - [1.1 ownership by part-number scheme](#11-ownership-by-part-number-scheme)
  - [1.2 identity](#12-identity)
  - [1.3 ownership per field and owner state](#13-ownership-per-field-and-owner-state)
  - [1.4 pdm overwrites mapped fields](#14-pdm-overwrites-mapped-fields)
  - [1.5 the owner flag](#15-the-owner-flag)
  - [1.6 released versions only](#16-released-versions-only)
  - [1.7 dual-owned fields](#17-dual-owned-fields)
- [2 made item fields](#2-made-item-fields)
  - [2.1 identity and revision](#21-identity-and-revision)
  - [2.2 cad-authored data](#22-cad-authored-data)
  - [2.3 glados-authored data](#23-glados-authored-data)
  - [2.4 system-managed](#24-system-managed)
  - [2.5 madeitemprocess](#25-madeitemprocess)
  - [2.6 madeitemfile](#26-madeitemfile)
  - [2.7 itempicture](#27-itempicture)
- [3 bought item fields](#3-bought-item-fields)
  - [3.1 field table](#31-field-table)
  - [3.2 claiming an existing bought item](#32-claiming-an-existing-bought-item)
- [4 lifecycle mapping](#4-lifecycle-mapping)
- [5 conflicts and parked events](#5-conflicts-and-parked-events)
- [6 enforcement](#6-enforcement)
  - [6.1 the ownership table and the revision policy](#61-the-ownership-table-and-the-revision-policy)
  - [6.2 read-only enforcement on cad rows](#62-read-only-enforcement-on-cad-rows)
  - [6.3 status and successor](#63-status-and-successor)
  - [6.4 where the settings live](#64-where-the-settings-live)
- [7 label properties and the feature-tree template](#7-label-properties-and-the-feature-tree-template)

## 1 principles in full

### 1.1 ownership by part-number scheme

- Glados keeps two number spaces side by side: its own internal formats and an external (PDM) part-number pattern, both configured in *Settings → Numbering*; internal formats may be shared between made and bought items, and so may the external pattern.
- Which catalogue a watched PDM file belongs to is decided by the watched folder it is found under; a `by_kind` folder instead reads it from the file's `kind` datacard property (`Glados.Kind` by default) once the variables are fetched.
- Saving the numbering settings is rejected if an internal format's rendered example matches the external pattern.
- With the integration enabled, creating or renumbering an item with a hand-typed number that matches the external pattern is rejected in the use cases, in the web, PAT and batch paths alike, because those numbers are reserved for PDM ingest.
- PDM-numbered rows are created and updated by ingest only.
- Glados-numbered rows, made items without a CAD model (weldments, parts manufactured from a drawing) and bought items before a PDM match, are Glados-owned.
- Ingest always keeps the PDM part number it reads, even with automatic part numbers switched on, since that setting only numbers web and PAT creations.
- When PDM's number for a linked file changes, ingest renumbers the linked rows to match; the old number stays registered and is never reused ([pdm-ingest.md section 4](pdm-ingest.md#4-renumbering)).
- Whether users may still create made or bought items in the web while the integration is enabled is an admin setting per kind (*Allow web creation of made items* and *of bought items*, default on); such items are Glados-numbered, and the setting never restricts ingest.
- A Glados-numbered made item is never claimed automatically, since it has no match key.
- When such a made item receives a CAD model, the PDM row is a new part, and the user either marks the old row `replaced` with the PDM item as successor (history stays separate) or merges it into the PDM item (history, files and references move, and the old row is deleted).
- A live bought item without a PDM link, created in the web or through the `pat` API, is claimed on a PDM match as described in [section 3.2](#32-claiming-an-existing-bought-item).

### 1.2 identity

- The part number is a label, not a key.
- In PDM one file is one part, and revisions are labels on versions of that file.
- Identity is per file: a file with several configurations maps to one Glados item, and parts that must be distinct items are distinct files.
- For made items the part is `(vault_id, pdm_file_id)` and the row is `(vault_id, pdm_file_id, revision)`, logically the same key as `(part_number, revision)`.
- For bought items there is one row per file, `(vault_id, pdm_file_id)`, and `revision` is data (the latest released one), not part of the key.
- The link columns live on every row, so the file id repeats across a part's revision rows, and they are also the address Glados uses to fetch from the PDM Web API.
- `public_id` is the outward handle for URLs, API paths and event payloads; it complements the link columns and cannot resolve a PDM file to a row.
- Part numbers are unique across the application, so a made-item family and a bought item never share a number, even when both kinds use the same scheme.
- The `part_number_registry` table (`part_number` unique, plus `kind`) enforces that uniqueness and is written in the same transaction as the item.
- A made-item family registers once, and revisions never touch the registry.
- A number is never reused while any row, archived rows included, carries it.
- An entry is freed once no row carries its number any more: a merge, a web or `pat` renumber and a bought-item claim that replaces the part number each release the old number on that condition.
- A renumber by PDM keeps the old number registered.

### 1.3 ownership per field and owner state

- Ownership applies only while the PDM integration is enabled; with it disabled every field is Glados-owned and the PDM-specific fields are ignored.
- With it enabled, the same field is web-editable on a Glados-owned row and read-only on a PDM-owned row, while Glados-only fields stay editable on PDM-owned rows.
- The rule is evaluated against `data_source` and enforced in the use cases (`create`, `update`, `merge`, `create_revision`, `IngestPdmFile`), never in the routes, so the web API, the PAT API, batch paths and ingest are covered equally.
- The admin override *CAD items read-only* (default on) can lift the web restriction on PDM-owned rows in an emergency; it does not change ownership or `data_source`, and the next ingest overwrites as usual.
- Whatever the settings, a new revision of a `CAD` made-item family comes only from PDM: `CreateMadeItemRevision` refuses it for every caller except the system user (`_assert_source_revisable`, `MadeItemRevisionManagedByPdmError`), even with the integration disabled or the override off.

### 1.4 pdm overwrites mapped fields

- PDM overwrites every mapped field unconditionally and never touches unmapped ones.
- There is no conflict detection and no merge, since the web is read-only on mapped fields of PDM-owned rows, so a PDM write can never lose a web edit.
- Which datacard variable feeds which field is an admin setting with separate maps for made and bought items ([pdm-settings.md section 4](pdm-settings.md#4-datacard-variable-maps)).
- Fields PDM has no datacard value for (`successor_item_id`, `files`) are never written by ingest.
- `status` has no datacard mapping and is driven by the file's workflow state on every ingest outcome that touches the row ([section 4](#4-lifecycle-mapping)).
- `approver_id` has no datacard mapping either; with `AdminPdmSettings.set_approver_from_pdm` on (default off), it is set from the file's workflow transition history and left untouched when the releaser does not resolve to a Glados user ([pdm-ingest.md section 5](pdm-ingest.md#5-pdm-releaser-attribution)).
- A payload for a known row is applied only if its `pdm_file_version` is higher than the stored one, or equal while the row's status differs from the one the file's workflow state maps to, since a workflow transition need not create a new file version.
- Redelivered and out-of-order events are ignored.
- Claiming a web-created bought item writes a changelog line naming the PDM file and the number of overwritten fields.
- "File missing or moved out of the released folders" is a sync state (`pdm_sync_state`), not a lifecycle status, so a row can be `replaced` and missing at once.
- An ingest that changes a field moves the row's edit version, so a web form open on the item meanwhile is refused with 409 instead of writing over what PDM just set. One that only stamps `pdm_file_version`, `pdm_synced_at` or `pdm_sync_state` leaves it alone ([persistence.md section 1.10](persistence.md#110-edit-versions-of-master-data)).

### 1.5 the owner flag

- `data_source` is the owner flag and changes one way only, from `WEB` to `CAD`.
- `CAD` rows are born from ingest, and a `WEB` bought item flips on a PDM match and never flips back.
- The web and `pat` create and update requests carry no `data_source` field and the update use cases never write it, so ingest is its only writer.
- The stored value `CAD` denotes data originating from the CAD system via PDM, and the user interface labels it "PDM".
- A flip replaces the part number with PDM's; if that number is already registered to another item, the claim is parked ([section 5](#5-conflicts-and-parked-events)).

### 1.6 released versions only

- `pdm_file_version` counts every check-in.
- A Glados revision row records the check-in version released as that revision, and a bought item records the version of its latest release.
- Ingest runs when the poller's diff finds a changed file or the trigger route names one, and the file's workflow state then gates what it does: a configured released state creates or updates the row, taking the revision label from `PDM.Revision` at that version; an obsolete or replaced state only sets `status`; any other state is skipped.
- A new Glados revision row is created only when `PDM.Revision` differs from the latest Glados revision of the file, through the same `CreateMadeItemRevision` path the web uses: Glados-owned fields are copied from the previous newest revision, CAD-owned fields come from the payload, and the predecessor status comes from the PDM predecessor setting.
- The same `PDM.Revision` at a higher file version updates, on the latest row, only the fields the revision policy marks "PDM: update in place", and the other fields wait for the next `PDM.Revision`.
- Old revision rows are never touched.
- Because only released data arrives, PDM-owned rows are born `active` (Glados' "released") and no separate draft or review state exists; Glados-owned rows are `active` on creation too.
- A made-item file without a `PDM.Revision` value is skipped as "identity variables missing", so a vault that does not manage revision labels cannot feed made items.

### 1.7 dual-owned fields

- A field that can legitimately be set both from the CAD file and in the web carries a PDM shadow value; today these are a made item's `source_item_id` and a bought item's `edp_part_id`.
- Next to the effective value, the row stores the value last received from PDM (`pdm_source_item_id`, `pdm_edp_part_id`).
- Ingest applies the PDM value to the effective field only when the PDM value itself changed since the last sync, and always updates the shadow.
- A web edit therefore survives every sync in which the CAD value is unchanged, and when the engineer changes the value in CAD, CAD wins.
- For `source_item_id` the web shows both values side by side with a "differs from CAD" indicator and an *apply CAD value* action.
- Dual-owned fields are excluded from read-only enforcement, since a web edit must stand until the CAD value itself changes ([section 6.2](#62-read-only-enforcement-on-cad-rows)).

## 2 made item fields

Entity: `src/modules/catalogue/domain/entities/made_item.py`. The editor and *Rev* columns are explained in the [FIELD_OWNERSHIP.md legend](../FIELD_OWNERSHIP.md#2-legend). The custom-property names are the defaults of the field mapping, not code, and the add-in's made-item properties are written against this table.

### 2.1 identity and revision

| Field | SW custom property | Editor | Rev | Notes |
|---|---|---|---|---|
| `part_number` | `PDM.PartNumber` | PDM | - | Label, not a key. Shared by all revisions of a part; unique together with `revision`; registered once per family in `part_number_registry`. Internal numbering for Glados-owned rows; a hand-typed number must not match the external pattern. |
| `revision` | `PDM.Revision` | PDM | - | Controlled revision string, numeric (`0`/`1`, `2`, …) or alphabetic (`A` … `Z`, `AA`, …). Not the PDM file version. Immutable on a row; a new revision is a new row. Web-created rows start at the configured start revision; the web "New revision" action increments, inferring the scheme from the current value. |
| `revision_date` | `PDM.RevisionDate` | PDM | no | Set on revision creation and editable in place afterwards. Unmapped or blank falls back to the releasing workflow transition's date ([pdm-ingest.md section 5](pdm-ingest.md#5-pdm-releaser-attribution)); a bought item has no equivalent field. |
| `revision_note` | `PDM.RevisionNote` | PDM | no | Set on revision creation and editable in place afterwards. Unmapped or blank falls back to the releasing transition's comment, like `revision_date`. |
| `public_id` | - | Server | - | UUID and outward-facing handle. |
| `vault_id` | - | PDM | - | Scopes `pdm_file_id`. Nullable, since `WEB` rows have no PDM file. |
| `pdm_file_id` | - | PDM | - | PDM document id, which is the part. Same value on every revision row of the part; row key `(vault_id, pdm_file_id, revision)`, a partial unique index where not null. |
| `pdm_file_version` | - | PDM | - | The check-in version released as this revision. Ordering and idempotency guard for ingest. |
| `pdm_synced_at` | - | PDM | - | When ingest last wrote this row. |
| `pdm_sync_state` | - | Server | - | Sync axis, independent of `status`: `synced`, `missing` or `conflict`. Shown as a badge; `missing` is treated like `inactive` for new work (demands, lots, order lines, substitutes). |

### 2.2 cad-authored data

| Field | SW custom property | Editor | Rev | Notes |
|---|---|---|---|---|
| `article_name` | `Glados.ArticleName` | Add-in | yes | A rename usually accompanies a design change. Required to create or revise a row; ingest never falls back to the PDM file's name ([pdm-ingest.md section 7](pdm-ingest.md#7-required-fields)). |
| `material` | `Glados.Material` | Add-in | yes | ISO material number, for example `1.0037`. Ingest stores the SolidWorks placeholder of a part without a material, such as `Material <not specified>`, as empty, so it never counts as a material that raw stock could mismatch. |
| `mass` | `Glados.Mass` | Add-in | yes | Grams. PDM column default: update in place. |
| `base_size` | `Glados.BaseSize` | Add-in | yes | Raw-stock size. |
| `note` | `Glados.Note` | Add-in | no | |
| `weblink` | `Glados.Weblink` | Add-in | no | |
| `article_group_ids` | `Glados.ArticleGroupIds` | Add-in | no | Classification, not design. |
| `bought_item_id` | `Glados.BoughtItemId` | Add-in | yes | Input material: buy this exact catalogue part. Mutually exclusive with `source_item_id`. |
| `source_item_id` | `Glados.SourceItemId` | Add-in / Web | yes | Input material: raw-stock specification. Dual-owned ([section 1.7](#17-dual-owned-fields)): shadow `pdm_source_item_id`, CAD wins only when the CAD value changes. |
| `processes` | `Glados.Processes` | Add-in | no | Manufacturing routing (`MadeItemProcess` rows, [section 2.5](#25-madeitemprocess)) authored in the CAD file including step groups. The encoding of steps and groups in the custom property is defined together with the add-in's made-item properties and honours the backend's grouping model (`group_index`). Edited in the web on Glados-owned rows. |
| `article_group_names` | `Glados.ArticleGroupNames` | Add-in | - | Not a column: a label next to `article_group_ids` ([section 7](#7-label-properties-and-the-feature-tree-template)). |
| `process_names` | `Glados.ProcessNames` | Add-in | - | Not a column: a label next to `processes` ([section 7](#7-label-properties-and-the-feature-tree-template)). |
| `source_item_name` | `Glados.SourceItemName` | Add-in | - | Not a column: a label next to `source_item_id` ([section 7](#7-label-properties-and-the-feature-tree-template)). |
| `customer_id` | `Glados.CustomerId` | Add-in | yes | The customer the part was received from, which makes the row a customer item. Archived customers are accepted. Web and `pat` writes need the customer part number with it; PDM ingest stores what the datacard holds and reads a dangling id as no customer. PDM column default: update in place. |
| `customer_part_number` | `Glados.CustomerPartNumber` | Add-in | yes | The customer's own part number. No key, since two customers may use the same number; never registered in `part_number_registry`. PDM column default: update in place. |
| `customer_revision` | `Glados.CustomerRevision` | Add-in | yes | The customer's own revision, independent of `revision`. PDM column default: update in place. |
| `customer_name` | `Glados.CustomerName` | Add-in | - | Not a column: a label next to `customer_id` ([section 7](#7-label-properties-and-the-feature-tree-template)). |
| `feature_tree_representation` | `Glados.FeatureTreeRepresentation` | Add-in | - | Not a column: the feature-tree template, resolved by SolidWorks ([section 7](#7-label-properties-and-the-feature-tree-template)). |
| `kind` | `Glados.Kind` | Add-in | - | Not a column: mappable so a `by_kind` watched folder can read which catalogue (`made` or `bought`) a file belongs to. Written once by the add-in and never changed afterwards; a later disagreement is a `conflict` outcome, never a silent kind change. |
| `glados_ids` | `Glados.Ids` | Server | no | Not a column: write-back only ([pdm-writeback.md](pdm-writeback.md)), a single-line JSON array of `{"revision", "public_id", "pdm_version"}` for every non-archived Glados row of the family, newest first. Version-free; ingest never reads it. |
| `newest_revision_sync_state` | `Glados.NewestRevisionSyncState` | Server | no | Not a column: write-back only. `synced`, `conflict: <reason>` or `skipped: <reason>` for the newest ingest outcome. Version-free; ingest never reads it. |
| `newest_revision_synced_at` | `Glados.NewestRevisionSyncedAt` | Server | no | Not a column: write-back only. ISO 8601 UTC timestamp of the last write-back. Version-free; ingest never reads it. |

### 2.3 glados-authored data

| Field | Editor | Rev | Notes |
|---|---|---|---|
| `status` | Web on a Glados-owned row; PDM on a CAD-owned row | no | `active`, `inactive` or `replaced`. `active` is Glados' "released": new work (a demand, a lot, an order line, a substitute) may only name an item that is active, not archived and whose PDM file is not `missing`, and a material reference needs an active item when it is set or changed. Work that already names an item keeps going when its status changes. Ingest sets `active` on creation and maps PDM lifecycle states ([section 4](#4-lifecycle-mapping)); on a CAD row, while the integration enforces ownership, `status` is read-only in the web like any other PDM-owned field. A status-only change is allowed on any revision, including non-newest ones. |
| `successor_item_id` | Web | no | Set when the row is `replaced`: the next revision's row, or the PDM item that supersedes a Glados-numbered part. The rules are in [section 6.3](#63-status-and-successor). |
| `approver_id` | Web | no | Reserved for an approval workflow. Also set by ingest from the file's workflow transition history, not a mapped variable, when `AdminPdmSettings.set_approver_from_pdm` is on ([pdm-ingest.md section 5](pdm-ingest.md#5-pdm-releaser-attribution)). |
| `files` | Web | no | Non-CAD attachments (`MadeItemFile`). Not copied to a new revision, since drawings come from PDM. |

### 2.4 system-managed

| Field | Editor | Notes |
|---|---|---|
| `id` | Server | Surrogate key; every revision row has its own. All references (demands, lots, processes, files) point here. |
| `data_source` | Server | `WEB` or `CAD`. Owner flag that changes from `WEB` to `CAD` only ([section 1.5](#15-the-owner-flag)). |
| `created`, `changed`, `changes`, `archived` | Server | `changes` receives a changelog line on ingest claims and revision creation. |
| `creator_id`, `changed_by_id` | Server | `changed_by_id` also reflects the resolved PDM releaser on a created, revised or status ingest outcome, in place of the system actor, when the transition's PDM user resolves to a Glados user ([pdm-ingest.md section 5](pdm-ingest.md#5-pdm-releaser-attribution)). |
| `source_label`, `source_sublabel` | Server | Read-only denormalisations. |
| `pdm_source_item_id` | Server | The `source_item_id` PDM last sent, written by ingest only ([section 1.7](#17-dual-owned-fields)). |

### 2.5 madeitemprocess

Entity: `src/modules/catalogue/domain/entities/made_item_process.py`. Authored through `Glados.Processes` on PDM-owned rows and in the web on Glados-owned rows. The web and ingest alike copy the steps one to one (order, grouping, estimates) onto a new revision.

| Field | Notes |
|---|---|
| `role` | `fabrication` or `inspection`. |
| `fabrication_method_id`, `inspection_method_id` | Exactly one is set, according to the role. |
| `position`, `group_index` | Step order and grouping. |
| `note` | |
| `estimated_setup_minutes`, `estimated_minutes_per_piece` | |
| `created`, `creator_id`, `made_item_id` | Server. |

### 2.6 madeitemfile

- The entity is `src/modules/catalogue/domain/entities/made_item_file.py`.
- `category` and the upload itself are Web, and the storage metadata (`stored_name`, `storage_path`, `sha256`, `size_bytes`, `mime_type`, `created`, `uploaded_by_user_id`) is Server.
- Files are not carried over to a new revision.
- Pictures are not files ([section 2.7](#27-itempicture)).

### 2.7 itempicture

Entity: `src/modules/catalogue/domain/entities/item_picture.py`, used by made, bought and source items. An item keeps at most one picture per source, and each source has its own editor, so no source can replace another.

| Source | Editor | Notes |
|---|---|---|
| `picture` | Web | A photo of the real object, uploaded and deleted by a person with the item's write permission. |
| `data_portal` | Server | Bought items only. Fetched for the EPLAN Data Portal part the item is linked to, replaced on a new link and removed on unlinking ([eplan-data-portal.md section 6](../EPLAN_DATA_PORTAL_INTEGRATION.md)). |
| `cad_rendering` | PDM | Made and bought items. An `image_and_thumbnail` document, else PDM's check-in thumbnail ([pdm-documents.md](pdm-documents.md)). |

- The picture shown for an item (tables, its page, printed documents) is the first of `picture`, `data_portal` and `cad_rendering` that exists.
- The thumbnail is always derived from the image, and the storage metadata is Server.
- Pictures are not carried over to a new revision.

## 3 bought item fields

### 3.1 field table

Entity: `src/modules/catalogue/domain/entities/bought_item.py`. There is one row per PDM file, and Glados keeps only the latest released revision. The add-in's `BoughtItemProperties` writes these custom properties.

| Field | SW custom property | Editor | Notes |
|---|---|---|---|
| `article_name` | `Glados.ArticleName` | Add-in | Required to create or claim a row; ingest never falls back to the PDM file's name ([pdm-ingest.md section 7](pdm-ingest.md#7-required-fields)). |
| `order_code_1` | `Glados.OrderCode1` | Add-in | Part of the exact bind key `(manufacturer_id, order_code_1)`. Required to create or claim a row. |
| `order_code_2` | `Glados.OrderCode2` | Add-in | |
| `gtin` | `Glados.Gtin` | Add-in | Unique. The strongest auto-bind key. |
| `ean` | `Glados.Ean` | Add-in | |
| `tariff_number` | `Glados.TariffNumber` | Add-in | |
| `mass` | `Glados.Mass` | Add-in | Grams. |
| `note` | `Glados.Note` | Add-in | |
| `weblink` | `Glados.Weblink` | Add-in | |
| `manufacturer_id` | `Glados.ManufacturerId` | Add-in | Picker in the task pane, backed by the supplier list. |
| `manufacturer_name` | `Glados.ManufacturerName` | Add-in | Not a column: a label next to `manufacturer_id` ([section 7](#7-label-properties-and-the-feature-tree-template)). Distinct from the API field `BoughtItemResponse.manufacturer_name` further down. |
| `article_group_ids` | `Glados.ArticleGroupIds` | Add-in | |
| `article_group_names` | `Glados.ArticleGroupNames` | Add-in | Not a column: a label next to `article_group_ids` ([section 7](#7-label-properties-and-the-feature-tree-template)). |
| `feature_tree_representation` | `Glados.FeatureTreeRepresentation` | Add-in | Not a column: the feature-tree template, resolved by SolidWorks ([section 7](#7-label-properties-and-the-feature-tree-template)). |
| `kind` | `Glados.Kind` | Add-in | Not a column: mappable so a `by_kind` watched folder can read which catalogue a file belongs to. Written once by the add-in and never changed afterwards; a later disagreement is a `conflict` outcome, never a silent kind change. |
| `glados_ids` | `Glados.Ids` | Server | Not a column: write-back only ([pdm-writeback.md](pdm-writeback.md)), a single-line JSON array with the one linked row's `{"revision": null, "public_id", "pdm_version"}`. Version-free; ingest never reads it. |
| `newest_revision_sync_state` | `Glados.NewestRevisionSyncState` | Server | Not a column: write-back only. `synced`, `conflict: <reason>` or `skipped: <reason>` for the newest ingest outcome. Version-free; ingest never reads it. |
| `newest_revision_synced_at` | `Glados.NewestRevisionSyncedAt` | Server | Not a column: write-back only. ISO 8601 UTC timestamp of the last write-back. Version-free; ingest never reads it. |
| `part_number` | `PDM.PartNumber` | PDM | PDM-generated, or internal numbering on Glados-owned rows. Unique across the application (registry). Replaced by PDM's number on a claim. |
| `revision` | `PDM.Revision` | PDM | Latest released revision of the file, overwritten on each release, `null` on `WEB` rows. Shown as a field, not inside the part-number label. |
| `status` | - | Web on a Glados-owned row; PDM on a CAD-owned row | `active`, `inactive` or `replaced`, with PDM lifecycle states mapped per [section 4](#4-lifecycle-mapping). Read-only in the web on a CAD row while the integration enforces ownership, as for made items. |
| `successor_item_id` | - | Web | Set when `replaced`. Same rules as for made items ([section 6.3](#63-status-and-successor)). |
| `product_family_id` | - | Web | The manufacturer's product family (cylinders, valves), a managed list beside the article groups. Glados-owned on every row and never written by ingest, so it stays editable on a CAD row. |
| `over_delivery_tolerance_percent`, `under_delivery_tolerance_percent` | - | Web | The item's own delivery tolerances, replacing the global ones of the order settings when set ([backend-conventions.md section 4](../CONTRIBUTING.md)). Glados-owned on every row and never written by ingest; a `pat` update leaves them as they are. |
| `edp_part_id` | `Glados.EdpPartId` | Add-in / Web | The EPLAN Data Portal part the item was created from or linked to. Set by the Data Portal create, import and lookup in the web and by the add-in's Data Portal lookup in the CAD file, never by the web form. Dual-owned ([section 1.7](#17-dual-owned-fields)): shadow `pdm_edp_part_id`, CAD wins only when the CAD value changes. A changed link requests the item's picture ([EPLAN_DATA_PORTAL_INTEGRATION.md](../EPLAN_DATA_PORTAL_INTEGRATION.md)). |
| `edp_synced_at` | - | Server | When the Data Portal part was linked or last read; cleared with the link. |
| `pdm_edp_part_id` | - | Server | The `edp_part_id` PDM last sent, written by ingest only. |
| `approver_id` | - | Web | Reserved for an approval workflow. Also set by ingest under the same `set_approver_from_pdm` rule as made items, with no difference per kind. |
| `files` | - | Web | Datasheets and the like. Not the CAD model. |
| `data_source` | - | Server | `WEB` or `CAD`. Owner flag that flips from `WEB` to `CAD` on a PDM match and never back. |
| `vault_id`, `pdm_file_id`, `pdm_file_version`, `pdm_synced_at`, `pdm_sync_state` | - | PDM / Server | As for made items; row key `(vault_id, pdm_file_id)`. |
| `public_id` | - | Server | UUID. |
| `id`, `created`, `changed`, `changes`, `archived`, `creator_id`, `changed_by_id` | - | Server | `changed_by_id` is the user behind the latest web or `pat` change, recorded by the session listener ([persistence.md section 1](../CONTRIBUTING.md)). A PDM ingest runs as a background job without an acting user and clears it. Unlike on made items, PDM releaser attribution reaches only the changelog text and `approver_id` here, never `changed_by_id`. |
| `manufacturer_name` (API field) | - | Server | Read-only denormalisation (`BoughtItemResponse.manufacturer_name`, joined from the linked manufacturer), unrelated to the `manufacturer_name` label row above. |
| `pdf_files` | - | Server | Read-only denormalisation. |

### 3.2 claiming an existing bought item

- A live bought row without a PDM link that already carries the incoming PDM part number is claimed first, directly on that match, because part numbers are unique app-wide and never reused, so that row is definitionally the same article.
- That part-number claim leaves the part-number registry untouched, since the number is already registered to the row.
- Failing that, a row is claimed on an exact key: `gtin`, or `manufacturer_id` plus `order_code_1`.
- Either claim flips `data_source`, overwrites all mapped fields and writes a changelog line, and the key-based claim also replaces the part number with PDM's.
- A row whose part number is already linked to a different PDM file is a conflict, not a claim.
- Without any match, ingest creates a new `CAD` bought item for the file.
- The exact checks and their order are in [pdm-ingest.md section 2.9](pdm-ingest.md#29-rule-9-bought-items).

## 4 lifecycle mapping

- Three settings per item kind map PDM workflow states onto `status` for PDM-owned rows: released states give `active`, obsolete states give `inactive`, and replaced states give `replaced` ([pdm-settings.md section 6](pdm-settings.md#6-lifecycle-state-lists)).
- A state outside all three lists is not watched, and the file is skipped.
- The three lists of a kind must be pairwise disjoint, so a workflow state drives at most one lifecycle status.
- `status` is PDM-owned on a CAD row while the integration enforces ownership, so a web or PAT caller cannot change it there.
- Whenever the resulting status is `active` or `inactive`, a `successor_item_id` already on the row is cleared with its own changelog line.
- A `replaced` target never touches the successor, because PDM carries no successor reference of its own; the successor stays a web decision, gated as described in [section 6.3](#63-status-and-successor).
- The made-item revise path keeps setting the previous revision's `status` to the configured PDM predecessor status and, when that resolves to `replaced`, its `successor_item_id` to the new revision, overriding a different successor a human had set, with a changelog note recording the override.
- When the predecessor ends `active` or `inactive` instead, a successor it still named is dropped with its own changelog line.
- A revision created in the web takes the predecessor status from the web predecessor setting (`revision_predecessor_status_web`), and the request's value only while that setting is `ask`.
- Rows whose file disappears from the vault or from the released folders get `pdm_sync_state = missing` and keep their status.
- The reconciliation report checks that the mapping stayed applied through its `status_mismatch`, `replaced_without_successor` and `successor_without_replaced` categories ([pdm-admin.md section 7.2](pdm-admin.md#72-categories)).

## 5 conflicts and parked events

- A PDM write is never applied when it would overwrite another item's identity.
- A renumbering whose target number is registered to a different item (a bought item, another made-item family, or an archived item whose number is still reserved) is parked.
- On a parked renumbering the old number stays, the row gets `pdm_sync_state = conflict`, and the event appears in the PDM pending list with the blocked target as its reason.
- No changelog line is written for a parked event, since nothing changed on the row.
- A parked event keeps its payload and is retried at the end of every sync run by reading the file fresh from PDM and ingesting it like any changed file ([pdm-sync.md section 3.9](pdm-sync.md#39-conflict-retries)).
- The retry needs no exemption from the version guard, because a row's `pdm_file_version` is never raised while it sits in conflict.
- Renumbering chains therefore resolve themselves, while swaps and genuine clashes wait for a human, who merges or replaces the other item or renumbers in PDM.

## 6 enforcement

### 6.1 the ownership table and the revision policy

- `src/modules/catalogue/domain/policies/item_field_ownership.py` holds the tables of this file as code.
- `item_fields()` returns the per-field ownership table, which `GetFieldMapping` serves and `UpdatePdmSettings` validates against.
- `default_policy()` and `web_blocked_changes()` implement the revision policy (`web_requires_revision` and `pdm_update_in_place` per field, defaults from the *Rev* column), and `UpdateMadeItem` uses them to reject an in-place change to a policy field.
- `src/modules/catalogue/domain/policies/revision_scheme.py` holds revision scheme detection, increment and ordering.
- `part_number_registry` enforces application-wide part-number uniqueness.

### 6.2 read-only enforcement on cad rows

- `src/modules/catalogue/domain/policies/pdm_ownership.py` is pure domain logic that implements the read-only rule.
- `pdm_owned_fields()` turns `item_fields()` into the set of fields a CAD row's web or PAT caller may never write, the fields with owner `pdm` or `addin`.
- Dual-owned fields (`source_item_id`, a bought item's `edp_part_id`) are excluded from `pdm_owned_fields()` entirely, since a web edit to them must stand until the CAD value changes.
- `blocked_pdm_owned_changes()` compares a proposed change set against that set and treats a list field such as `article_group_ids` as an unordered set, so reordering is not a false positive.
- `assert_cad_row_writable()` raises `PdmOwnedFieldReadOnlyError`, naming the blocked fields, once both sets are non-empty.
- Whether enforcement applies at all is the calling use case's decision: `UpdateMadeItem` and `UpdateBoughtItem` ask Catalogue's CAD source port (`src/modules/catalogue/ports/outbound/cad_source_port.py`) for its `CadPolicy`.
- `CadPolicy.enforces_ownership_for(actor)` is `rows_read_only and not actor.is_systemuser`, and PDM's implementation (`PdmCadSource`) sets `rows_read_only` to `is_pdm_enabled(pdm) and pdm.cad_items_read_only`.
- The check is therefore a no-op while the integration is off or unconfigured, and an admin can lift it in an emergency through *CAD items read-only* without changing `data_source` or field ownership.
- Ingest always acts as the system user, so `actor.is_systemuser` exempts it, and PDM's own writes are never blocked by the rule that protects PDM-owned data from everyone else.
- `status` carries owner `pdm` in `item_fields()`, because it is driven by the workflow state, so the same mechanism covers it with no extra code and a change raises `PdmOwnedFieldReadOnlyError`.
- The frontend disables the same fields in the single-item edit dialogs from the server-computed `pdm_locked_fields` list on each item response (`frontend/src/shared/utils/pdmOwnedFields.ts`), but the server-side check is the authoritative one.
- The bulk-edit forms do not mirror this lock yet ([PDM_INTEGRATION.md section 8](../PDM_INTEGRATION.md#8-limits-and-open-points)).

### 6.3 status and successor

- `successor_item_id` stays owner `web`, so it is settable and clearable on a CAD row.
- `UpdateMadeItem` and `UpdateBoughtItem` add one check next to `assert_cad_row_writable`: on a CAD row, while enforcement applies, assigning a successor (a non-null value that actually changes) is rejected with `PdmSuccessorRequiresReplacedStatusError` (409) unless the row's current `status` is already `replaced`.
- The row cannot flip its own status to `replaced` in the same write to make the assignment valid, since `status` is locked; the file must first move to a configured replaced workflow state in PDM.
- Clearing a successor is never gated by this check.
- Web-owned rows, and a CAD row while enforcement is off, are unaffected by either rule.
- Independently of ownership, `src/modules/catalogue/domain/policies/catalogue_item_status.py` checks status and successor together on every web and PAT write of a catalogue item (`assert_catalogue_status_change`, run by the update and create use cases and the revise path after the PDM ownership checks).
- A move to `replaced` needs a successor of the same catalogue that exists (`CatalogueSuccessorNotFoundError`, 404, otherwise), is not archived and does not lead back to the row.
- Only a `replaced` row names a successor, and a move to `active` or `inactive` drops it; a combination that does not fit raises `CatalogueStatusChangeError` (409).
- A write that changes neither status nor successor leaves an older inconsistent row as it is, and a row is never created `replaced`.
- On a CAD row under enforcement the status stays PDM's, so clearing the successor of a `replaced` row stays allowed there; where the caller owns the status, a `replaced` row keeps its successor until it moves to `active` or `inactive`.
- A status change through an update use case publishes `MadeItemStatusChanged`, `BoughtItemStatusChanged` or `SourceItemStatusChanged`.
- The same module's `demandable_refusal` backs each catalogue's `assert_item_demandable`, the check every path runs that newly names an item for new work.
- PDM ingest's workflow-state flips set a CAD row's status by their own rules and are not checked by `catalogue_item_status.py`; the items ingest creates and the revisions it makes run through the same use cases and are checked.

### 6.4 where the settings live

- The *Numbering* settings live on `AdminMadeItemSettings` and `AdminOrderSettings`, one per kind: the internal formats, the external pattern (`pdm_part_number_pattern`), the web-creation toggles, and for made items the start revision, the separator and the predecessor status for web and PDM.
- The revision policy is one list on `AdminMadeItemSettings` (`revision_field_policy`); its *web_requires_revision* half is edited under *Numbering* and its *pdm_update_in_place* half under *Settings → SolidWorks PDM*.
- The same PDM screen edits the single `admin_pdm_settings` row ([pdm-settings.md](pdm-settings.md)).

## 7 label properties and the feature-tree template

- Five fields exist only as labels next to a mapped id field, so datacards, BOMs and PDM search can show names instead of numbers.
- They are `article_group_names` (made and bought, from `article_group_ids`), `manufacturer_name` (bought, from `manufacturer_id`), `process_names` (made, from `processes`), `source_item_name` (made, from `source_item_id`) and `customer_name` (made, from `customer_id`, the customer's name from the add-in's lookup snapshot).
- None of the five is an item column and none is ever ingested; ingest ignores them like any other unmapped variable.
- Otherwise each label is a normal mappable, add-in-owned row that an admin gives its own custom property name in the field-mapping settings.
- The add-in composes `source_item_name` at save time from its lookup snapshot of the picked source item (type name, dimension and material, empty parts skipped); the add-in never reads it back and the backend never resolves it.
- `feature_tree_representation` (both kinds, the same field name in both maps) is a further mappable row that labels nothing: it holds a summary the feature tree, BOMs and the datacard show.
- Its value comes from the settings `made_feature_tree_template` (default `$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")`) and `bought_feature_tree_template` (default `$PRP:"Glados.ArticleName" - $PRP:"Glados.OrderCode1" - $PRP:"Glados.ManufacturerName"`).
- The add-in writes the template verbatim as the property's value, and SolidWorks resolves each `$PRP:"name"` link to another custom property itself.
- Neither Glados nor the add-in renders anything, so the summary follows a later change to any linked property, such as a part number or revision PDM assigns at check-in or release, without the file being saved again.
- A link names a custom property, not a Glados field, so it does not follow a later rename in the field mapping, and a link to a property that does not exist resolves to nothing.
- `validate_feature_tree_template` (`src/modules/external_data/domain/services/feature_tree_template.py`) rejects a template with a line break or another control character, one longer than 255 characters, and one linking to the property it is written into (the kind's `feature_tree_representation` mapping).
- `UpdatePdmSettings` enforces it on save through `AdminPdmSettings.assert_feature_tree_templates_valid` (`PdmSettingsInvalidError`, 400).
- Any other link is accepted, since it may name a SolidWorks property Glados does not map; the settings page only warns about one.
- `item_fields()` carries the label rows and `feature_tree_representation` like any other field, and `label_of` names a label's source field (null for a real column and for `feature_tree_representation`).
- `addin_written_fields(kind)` is the exclusion set that keeps `pdm_variables.map_variables()` and `pdm_required_fields.required_field_candidates()` from treating one of them as a PDM-mapped item column, however it is mapped.
- The wire, both `GET` and `PUT /admin/settings/pdm` and the PAT field-mapping response, serves them as ordinary entries with `label_of` set, plus a `templates` block for the two feature-tree templates.
- Saving the field mapping validates their variable names with the same unknown-field and duplicate-variable rules as any other field, and nothing extra.
