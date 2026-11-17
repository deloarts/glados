# eplan data portal

The calls Glados makes to the EPLAN Data Portal, the manufacturer mapping, how a part fills a bought item, the rules of every entry point including the add-in lookups and PDM ingest, the ownership of the linked fields, the picture worker and the spreadsheet import settings. The guide [EPLAN_DATA_PORTAL_INTEGRATION.md](../EPLAN_DATA_PORTAL_INTEGRATION.md) explains the integration.

- [eplan data portal](#eplan-data-portal)
  - [1 portal calls](#1-portal-calls)
  - [2 settings and manufacturer codes](#2-settings-and-manufacturer-codes)
  - [3 how a part fills an item](#3-how-a-part-fills-an-item)
  - [4 entry points](#4-entry-points)
    - [4.1 search in the create dialog](#41-search-in-the-create-dialog)
    - [4.2 import from a file](#42-import-from-a-file)
    - [4.3 lookup on an item](#43-lookup-on-an-item)
    - [4.4 the add-in lookups](#44-the-add-in-lookups)
    - [4.5 PDM ingest of the part id](#45-pdm-ingest-of-the-part-id)
  - [5 ownership of the linked fields](#5-ownership-of-the-linked-fields)
  - [6 pictures](#6-pictures)
  - [7 data import settings](#7-data-import-settings)

## 1 portal calls

- The port is `IEplanDataPortal` in the `external_data` module, implemented by the `eplan_data_portal` adapter with an httpx client and a client cache per connection.
- Every call is authenticated with the organisation's personal access token as `Authorization: Bearer PAT:<token>`.
- Batch calls send numbers or ids as `text/plain` and are chunked: one exact lookup of up to 100 numbers, then one read of up to 50 parts with every relation included.
- Glados never writes to the portal, the user's download list included.
- How the token is protected (encryption, no redirects, https only) is in [the guide's section 9](../EPLAN_DATA_PORTAL_INTEGRATION.md#9-security).

## 2 settings and manufacturer codes

- The switch needs a token, and removing the token switches the lookups off.
- The token is write-only, and the API answers `pat_configured`, never the value.
- The connection test is an authenticated read of the download list.
- The article name language is German or English, with the other one as fallback.
- A supplier's portal manufacturer code (SIE for Siemens, FES for Festo) is stored upper case and is unique among live suppliers.
- A supplier with *Type number is order code 1* swaps order and type number wherever the portal fills an item.
- The portal's exact number check finds a part by either number, so the import and the lookup on an item work the same with the swap.

## 3 how a part fills an item

`edp_item_draft.py` decides this for every entry point.

| Item field | From the part |
| ---------- | ------------- |
| article name | The designation in the configured language, else the other one, else the description. |
| order code 1 | The order number, or the type number when the manufacturer's supplier puts the type number first. |
| order code 2 | The other one of the two, when it differs from order code 1. |
| EAN | The identcode when it is an EAN. |
| weblink | The manufacturer's support link, else the part's own portal page. |
| manufacturer | The supplier carrying the part's manufacturer code, never guessed from a name. |
| product family | The live family named like the deepest product group, in any case. |
| article groups | The default article groups of the settings. |
| `edp_part_id`, `edp_synced_at` | The part id and the time it was read. |

- Order codes are compared in the form of `normalize_order_code`, which ignores case, whitespace and the separators space, dash, dot, slash and underscore, so `3RT2015-1BB41` finds `3rt20151bb41`.
- Stored values are never changed by the normalisation.

## 4 entry points

### 4.1 search in the create dialog

- `GET /bought-items-edp/search` returns ranked hits, each with the values it fills and the catalogue item that already describes it, found by portal link or by manufacturer and order code.
- Picking a hit fills the form, and saving sends `edp_part_id`, so the create links the part and requests its picture.
- The search and the part picture need `use:data_portal`; saving the item still needs `write:bought_items`.
- Without `use:data_portal` the search field stays visible but disabled, its tooltip names the missing permission, and a part picture shows the placeholder without a request.

### 4.2 import from a file

- `POST /bought-items-import/validate` and `/commit` take the parsed rows and a `lookup` flag.
- Without the lookup a row names its manufacturer, article groups and product family, resolved by name.
- With the lookup every row is looked up by its EPLAN part number, else its order code; the portal wins for every field it supplies, the file fills the rest, and each disagreement is listed per row.
- A row the portal does not know is `not_found`, and the user creates it from the file alone.
- Several hits make a row `ambiguous`, and the user picks one.
- A manufacturer without a supplier code makes a row `invalid`.
- Every row is then checked against the catalogue and by the single create's own checks.
- Commit re-resolves everything, creates the ready rows and links the existing items in one transaction, and names the rows it handled; the rest stay in the draft.
- The row limit comes from the data import profile (section 7).

### 4.3 lookup on an item

- `GET /bought-items-edp/items/{id}/lookup` finds the item's part by its link, by a given `part_id`, else by its order code narrowed to its manufacturer's code, and compares it field by field.
- `POST .../apply` writes the chosen fields through `UpdateBoughtItem`, then links the part and requests its picture.
- Both need `write:bought_items`, since they work on an item the user may change.

### 4.4 the add-in lookups

The add-in never writes a bought item to Glados, so its lookups on the `pat` surface only read.

- `GET /bought-items-edp/status` says whether the portal is switched on, so the add-in can hide its lookup otherwise.
- `GET /bought-items-edp/match?number=` returns the parts an order, type or EPLAN part number names exactly, in the shape of the search: the part, the values it fills and the catalogue item that already describes it.
- A `manufacturer_id` narrows several match hits to that supplier's portal code.
- `GET /bought-items-edp/search?q=` is the create dialog's ranked search.
- `GET /bought-items-edp/parts/{id}/picture` passes the picture through.
- The match, the search and the picture need `use:data_portal`, as the create dialog's search does, since every call spends the organisation's portal token. The status needs only a valid token.
- The SolidWorks add-in token preset carries `use:data_portal` next to `write:source_items` (`SOLIDWORKS_ADDIN_SCOPES` in `token_permission_rules.py`), so a preset token reaches these lookups whenever its owner holds the permission.
- The MCP tool `edp_lookup` runs the same match and search and needs the same permission.

### 4.5 PDM ingest of the part id

- What the engineer takes from a part goes into the file's add-in-owned properties, and its part id into `Glados.EdpPartId`, the default variable of the bought `edp_part_id` field in the PDM field mapping.
- The vault's bought datacard needs a variable for it like for any other mapped field.
- Ingest relinks the item only when the file's value differs from the one it read last time (`pdm_edp_part_id`), so a link made in the web survives every sync of a file that does not change it.
- A changed value links the item and an emptied one unlinks it, each with a changelog line, and a new link requests the picture like any other.
- The part id is checked for its form only, by ingest and by the pre-release validation, and neither asks the portal.

## 5 ownership of the linked fields

- An item already in the catalogue is treated as correct: the search and the import never change it and report where the file or the portal differs.
- The lookup on an item goes through the normal update, so a field PDM owns on a CAD row ([FIELD_OWNERSHIP.md](../FIELD_OWNERSHIP.md)) is shown but cannot be taken; it is changed in the SolidWorks file.
- `edp_part_id` is dual-owned (FIELD_OWNERSHIP.md principle 7): the web's portal paths write it on WEB and CAD rows alike, and ingest writes it from the file under the shadow rule of section 4.5, so neither silently undoes the other.
- `edp_synced_at` and `product_family_id` are Glados-owned on every row.
- A web item created from the portal is a normal `WEB` row that PDM claims later like any other.

## 6 pictures

- Creating, importing or linking an item, and a link PDM ingest makes or removes, publishes `BoughtItemEdpPictureRequested`.
- The `edp_pictures` consumer group on the events stream reads the part again by the item's own link, downloads the picture and stores it through `ItemPictureStore` as the system user.
- The picture is an `ItemPicture` of source `data_portal` (field-ownership.md section 2.7), beside a photo a person uploaded and the CAD rendering from PDM, and replaces neither.
- The item shows the photo first, then the Data Portal picture, then the CAD rendering.
- A picture already fetched for the same part is kept, a new part replaces it, and an item without a link loses it.
- Nothing happens while storage or the portal is off.
- A change to an item's pictures sends a live signal on `bought-items`, so open pages show the picture without a reload.
- The browser never loads the portal's blob storage directly, because the content security policy allows same-origin images only; previews go through `GET /bought-items-edp/parts/{id}/picture`.

## 7 data import settings

- *Settings, Data import* holds one profile per spreadsheet import: bought item create, bought item demands and made item demands.
- A profile holds the header row (detected or fixed), how many rows below it the data starts, the row limit (default 100, at most 1000) and the column names per field.
- A fresh install seeds the profiles with no column names. The recommended names, one file per language, are imported by the admin from the root `templates/data-import/` folder.
- Detection scores the first 20 non-empty rows by how many fields their cells name.
- A header that misses a required column opens the manual mapping for that one upload.
- Parsing happens in the browser, and the backend enforces the row limit again on validate and commit.
