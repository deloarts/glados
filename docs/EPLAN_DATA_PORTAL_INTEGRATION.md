# eplan data portal integration

- [eplan data portal integration](#eplan-data-portal-integration)
  - [1 purpose and scope](#1-purpose-and-scope)
  - [2 components and data flow](#2-components-and-data-flow)
  - [3 configuration](#3-configuration)
  - [4 how a part fills an item](#4-how-a-part-fills-an-item)
  - [5 the entry points](#5-the-entry-points)
  - [6 existing items and pdm ownership](#6-existing-items-and-pdm-ownership)
  - [7 pictures](#7-pictures)
  - [8 data import settings](#8-data-import-settings)
  - [9 security](#9-security)
  - [10 limits and open points](#10-limits-and-open-points)

## 1 purpose and scope

The EPLAN Data Portal is EPLAN's public catalogue of manufacturer parts. Glados reads from it to create bought items with less typing and to keep existing ones close to the manufacturer's data. It never writes to the portal.

What the portal supplies: designation and description texts in several languages, order and type number, EAN, the manufacturer and its portal code, the EPLAN product group path, the manufacturer's support link and a 512 px product picture. What it does not supply, so Glados keeps asking for it: mass, customs tariff number, price, STEP or STL models. Datasheet PDFs are only relative paths inside the portal and are not fetched.

## 2 components and data flow

The integration lives in the `external_data` module (`backend/src/modules/external_data/`): a port with an httpx adapter, one service that turns a part into item values, one that links an item to a part, and use cases for the import, the lookup on an item and the picture. The web surface has the settings, the import and the portal routes; the `pat` surface has read-only lookups for the SolidWorks add-in. PDM ingest links an item to the part its file names, and a worker on the events stream fetches pictures. Every call to the portal carries the organisation's personal access token, and lookups are batched. Its state lives in `admin_edp_settings` and `admin_data_import_settings`, in the bought item columns `edp_part_id`, `edp_synced_at` and `pdm_edp_part_id`, in the supplier columns `edp_code` and `edp_type_number_first`, and in the portal pictures of `item_picture_table`.

Full rules: [reference/eplan-data-portal.md section 1](reference/eplan-data-portal.md#1-portal-calls).

## 3 configuration

*Settings, EPLAN Data Portal*, beside SolidWorks PDM:

- **Use the EPLAN Data Portal** switches every entry point on. It needs a token.
- **API address** is the portal's API, `https://dataportal.eplan.com/api` by default.
- **Personal access token** is created for the Data Portal in the ePulse profile of an organisation (not the ePulse Community). A token expires, and the connection test shows when it no longer works.
- **Article name language** is German or English.
- **Default article groups** are given to every item created from the portal.

Each manufacturer the portal knows must be mapped once: its supplier gets the portal's manufacturer code (SIE for Siemens, FES for Festo) in the supplier form. Some manufacturers name their parts by type number first (Festo: order code 1 `DFM-25-50-P-A-GF`, order code 2 `170851`); for them the supplier's *Type number is order code 1* swaps the two numbers.

Full rules: [reference/eplan-data-portal.md section 2](reference/eplan-data-portal.md#2-settings-and-manufacturer-codes).

## 4 how a part fills an item

One service decides for every entry point which item field takes which part value: article name, both order codes, EAN, weblink, manufacturer, product family, the default article groups and the part link. The manufacturer is always the supplier carrying the part's manufacturer code, never a guess from a name. Order codes are compared ignoring case, whitespace and common separators, so `3RT2015-1BB41` finds `3rt20151bb41`.

Full rules: [reference/eplan-data-portal.md section 3](reference/eplan-data-portal.md#3-how-a-part-fills-an-item).

## 5 the entry points

- **Search in the create dialog.** A ranked search fills the bought item form from a picked part and shows the catalogue item that already describes it.
- **Import from a file.** A spreadsheet import can look up every row in the portal; the portal wins for what it supplies, the file fills the rest, and rows the portal does not know or cannot decide are left to the user.
- **Lookup on an item.** An existing item is compared with its part field by field, and the user takes the fields they want.
- **The SolidWorks add-in and PDM ingest.** The add-in never writes a bought item to Glados. Its lookups only read, through the `pat` routes, and the engineer writes what they take into the SolidWorks file, including the part id in `Glados.EdpPartId`. PDM ingest then brings the file and its link to the catalogue.

The search, the add-in's match and a part's picture need the permission `use:data_portal`, since every call spends the organisation's portal token, and the SolidWorks add-in's token preset carries it. Creating an item from a hit, the import, and the lookup on an item with its apply action need the bought item write permission, since they work on the catalogue itself.

Full rules: [reference/eplan-data-portal.md section 4](reference/eplan-data-portal.md#4-entry-points).

## 6 existing items and pdm ownership

An item already in the catalogue is treated as correct. The search and the import never change it; where the file or the portal differs, they say so. The lookup on an item is the one place where a user takes portal values on purpose, and it respects PDM ownership ([FIELD_OWNERSHIP.md](FIELD_OWNERSHIP.md)): a field PDM owns on a CAD row is changed in the SolidWorks file. The part link is owned by both sides, and a shadow column lets ingest change it only when the file's value changes, so neither silently undoes the other.

Full rules: [reference/eplan-data-portal.md section 5](reference/eplan-data-portal.md#5-ownership-of-the-linked-fields).

## 7 pictures

Linking an item to a part, by any path, requests its picture, and a worker fetches it in the background and stores it as the item's Data Portal picture. It sits beside an uploaded photo and the CAD rendering and replaces neither; the item shows the photo first, then the Data Portal picture, then the CAD rendering. The browser never loads the portal's storage directly.

Full rules: [reference/eplan-data-portal.md section 6](reference/eplan-data-portal.md#6-pictures).

## 8 data import settings

*Settings, Data import* holds one profile per spreadsheet import (bought item create, bought item demands, made item demands): where the header row is, where the data starts, the row limit and the column names per field. Glados detects the header from the column names, and a file that misses a required column opens a manual mapping for that upload. Parsing happens in the browser.

Full rules: [reference/eplan-data-portal.md section 7](reference/eplan-data-portal.md#7-data-import-settings).

## 9 security

- The token is encrypted at rest ([ADR 0005](adr/0005-secret-encryption-at-rest.md)), never returned, never logged, and audited only as "replaced".
- Redirects are not followed, so the token cannot travel to another host; the picture download goes to the blob host without the token.
- Only https is accepted for the API address.
- A picture is fetched only for a part an item is linked to, and is processed by the same image pipeline as an upload.

## 10 limits and open points

- The portal's API is the backend of its website. It is documented but has no service agreement; EPLAN may change it.
- `product_family_id` is not mapped to a PDM datacard variable yet. Doing so needs ingest, the add-in lookups on the `pat` surface and the add-in to change together.
- Ingest never checks a datacard's part id against the portal. An id the portal does not know links the item without a picture, and the next lookup on the item shows it.
- Datasheets, DXF and 3D data are not taken.
