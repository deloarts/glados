# Field Ownership, Glados ↔ SolidWorks PDM

- [1. Principles](#1-principles)
- [2. Legend](#2-legend)
- [3. MadeItem](#3-madeitem)
- [4. BoughtItem](#4-boughtitem)
- [5. SourceItem](#5-sourceitem)
- [6. Lifecycle mapping](#6-lifecycle-mapping)
- [7. Conflicts and parked events](#7-conflicts-and-parked-events)
- [8. Enforcement](#8-enforcement)
- [9. Label properties and the feature-tree template](#9-label-properties-and-the-feature-tree-template)

Status: implemented. The revision model, the part-number registry and the numbering settings live in the made-item catalogue; the PDM connection, poller, trigger endpoint, ingest and read-only enforcement live in the PDM integration ([PDM_INTEGRATION.md](PDM_INTEGRATION.md)).

Three systems hold overlapping data about the same physical part. **PDM** is the system of record for CAD files and their controlled revisions. **Glados** is the catalogue and planning system, downstream of PDM. The **SolidWorks add-in** runs at the workstation, shows the engineer how the open document differs from Glados and edits the document's custom properties. It never creates a made or bought item and never authors their data in Glados; the only item it creates is a source item, through the `pat` API. The `pat` API also has create and update routes for bought items, for scripts and other tools. This guide states the principles and the vocabulary; [reference/field-ownership.md](reference/field-ownership.md) holds the per-field tables and the complete rules.

---

## 1. Principles

1. **PDM is the single source of truth for CAD data; ownership is decided by the part-number scheme.** Glados keeps two number spaces side by side, its own internal formats and an external (PDM) pattern, both in *Settings → Numbering*. While the integration is enabled, numbers that match the external pattern are reserved for PDM ingest, and rows carrying them are created and updated by ingest only. Glados-numbered rows (made items without a CAD model, bought items before a PDM match) are Glados-owned. A Glados-numbered made item is never claimed automatically, while a bought item is claimed when PDM delivers a file that matches it.
2. **Identity is per file, and the part number is a label, not a key.** In PDM one file is one part, and revisions are labels on versions of that file. A made item's part is `(vault_id, pdm_file_id)` and each revision is its own row; a bought item is one row per file, with `revision` as data. Part numbers are unique across the whole application, across both kinds, and are never reused while any row, archived rows included, still carries them. A merge or a web or `pat` renumber frees a number once no row carries it any more, while a renumber by PDM keeps the old number registered.
3. **Ownership is per field and owner state, and applies only while the integration is enabled.** The same field is web-editable on a Glados-owned row and read-only on a PDM-owned row, and Glados-only fields stay editable everywhere. The rule is enforced in the use cases, so web, PAT, batch paths and ingest are covered alike, and an admin override can lift the web restriction in an emergency without changing ownership.
4. **PDM overwrites every mapped field unconditionally and never touches unmapped ones.** Since the web cannot edit those fields on a PDM-owned row, there is no conflict detection and no merge. A payload is applied only when its file version is newer than the row's, or when it changes the row's workflow status, so redelivered and out-of-order events are harmless.
5. **`data_source` is the owner flag and changes one way only, `WEB → CAD`.** `CAD` rows are born from ingest, and a `WEB` bought item flips when PDM claims it and never flips back. The user interface labels `CAD` as "PDM".
6. **Glados only ingests released versions.** A file's workflow state gates what ingest does: a released state creates or updates the row, an obsolete or replaced state only sets the status, and any other state is skipped. A new made-item revision row is created only when `PDM.Revision` changes; a new check-in under the same revision updates only the fields the revision policy allows in place.
7. **Dual-owned fields carry a PDM shadow value.** A field that can be set both in CAD and in the web (a made item's `source_item_id`, a bought item's `edp_part_id`) remembers the value PDM last sent. A web edit survives every sync in which the CAD value is unchanged; when the engineer changes it in CAD, CAD wins.

Full rules: [reference/field-ownership.md section 1](reference/field-ownership.md#1-principles-in-full).

## 2. Legend

The editor column applies **only while the PDM integration is enabled**. With the integration disabled, every field is Glados-owned and editable in the web, and the PDM fields are ignored.

| Editor | Meaning |
|---|---|
| **Add-in** | Authored in the SolidWorks custom property. Reaches Glados via PDM ingest. Read-only in the web on PDM-owned rows; web-editable on Glados-owned rows. |
| **PDM** | Set by PDM itself (numbering, revisioning, vault identity). Nobody edits directly. On Glados-owned rows Glados plays the PDM role (internal numbering, web revisioning). |
| **Add-in / Web** | Dual-owned; principle 7 applies. |
| **Web** | Glados web UI. No CAD counterpart; ingest never writes these. |
| **Server** | System-managed. Not editable from either surface. |

The **Rev** column (made items) shows the **default** of the configurable *revision policy*, two independent toggles per field: the web toggle under *Settings → Numbering → Revisions*, the PDM toggle under *Settings → SolidWorks PDM*.

- **Web, requires new revision** (`yes`): on a Glados-owned made item the field is disabled in the edit dialog and in bulk edit and is writable only in the *New revision* form, which creates the next revision row with the changed values; `no` means it is edited in place. The server rejects an update that changes a `yes` field on the current row.
- **PDM, update in place**: when PDM delivers a new file version under the same `PDM.Revision`, fields flagged "update in place" are overwritten on the latest Glados revision row at once, and the others wait for the next `PDM.Revision`, which always creates a new row. The default is the inverse of the web column with two exceptions: `mass` is both, since PDM recomputes it on every save while a web user changing the mass declares a design change, and `processes` is neither, since the web edits the routing in place and a PDM routing change waits for the next `PDM.Revision`.
- **-** means not applicable (the revision itself, identity, or system-managed).

The SolidWorks custom-property names in the tables are the **defaults of the field mapping** (*Settings → SolidWorks PDM*), not code.

---

## 3. MadeItem

A made item's identity and revision fields (`part_number`, `revision`, the revision date and note, and the PDM link columns) belong to PDM. Its design data (article name, material, mass, input material, routing, customer data) is authored by the add-in in the CAD file. Its lifecycle and workflow data (`status`, `successor_item_id`, `approver_id`, attachments) belong to Glados, with `status` following the PDM workflow on a CAD-owned row. The routing steps, attachments and pictures are sub-entities; an item shows at most one picture per source (a photo, the EPLAN Data Portal picture, the CAD rendering), each with its own editor.

Full rules: [reference/field-ownership.md section 2](reference/field-ownership.md#2-made-item-fields).

## 4. BoughtItem

A bought item is one row per PDM file, and Glados keeps only its latest released revision. Its article data comes from the add-in, its part number and revision from PDM, and Glados keeps its lifecycle, product family, delivery tolerances and attachments. A bought item that exists in Glados before PDM knows it is claimed by the first matching file: on its part number first, then on `gtin` or on manufacturer and order code. The claim flips it to `CAD`, overwrites all mapped fields and gives it PDM's part number.

Full rules: [reference/field-ownership.md section 3](reference/field-ownership.md#3-bought-item-fields).

## 5. SourceItem

Glados owns source items completely (all fields Web). The add-in may only reference one from a made item (`MadeItem.source_item_id`).

---

## 6. Lifecycle mapping

PDM workflow states are mapped onto `status` for PDM-owned rows by three settings per item kind: *released states* (→ `active`), *obsolete states* (→ `inactive`) and *replaced states* (→ `replaced`); a state outside all three is not watched. PDM carries no successor reference, so the successor of a replaced row stays a web decision, and ingest clears a stale successor when it moves a row back to `active` or `inactive`. A file that disappears from the vault marks its row `missing` on a separate sync axis and leaves the status alone.

Full rules: [reference/field-ownership.md section 4](reference/field-ownership.md#4-lifecycle-mapping).

## 7. Conflicts and parked events

A PDM write is never applied when it would overwrite another item's identity. A renumbering whose target number belongs to a different item is parked as a conflict; the row keeps its old number and the event waits on the PDM pending list. Parked events are retried at the end of every sync run, so renumbering chains resolve themselves, while swaps and genuine clashes wait for a human to merge, replace or renumber.

Full rules: [reference/field-ownership.md section 5](reference/field-ownership.md#5-conflicts-and-parked-events).

## 8. Enforcement

The tables of the reference file exist as code in `src/modules/catalogue/domain/policies/item_field_ownership.py`, which also implements the revision policy. `pdm_ownership.py` in the same package turns the table into the set of fields a CAD row's web or PAT caller may not write, and the update use cases apply it whenever the integration is enabled and *CAD items read-only* is on. Ingest acts as the system user and is exempt. Status and successor are checked together on every web and PAT write.

Full rules: [reference/field-ownership.md section 6](reference/field-ownership.md#6-enforcement).

## 9. Label properties and the feature-tree template

Some ids in the CAD file are meaningless to a person reading a data card or a BOM, so the add-in writes a name next to them: the article group names, the manufacturer name, the process names, the source item name and the customer name. A further property, the feature-tree representation, holds a summary built from an admin-configured template whose `$PRP:"name"` links SolidWorks resolves itself, so the summary stays current when PDM assigns a part number or revision. These properties are mappable like any other field, but they are not item columns and ingest never reads them.

Full rules: [reference/field-ownership.md section 7](reference/field-ownership.md#7-label-properties-and-the-feature-tree-template).
