---
title: Importing Bought Items from a File
summary: How to create many bought items from an Excel sheet, what the review tells you about each row, and how the EPLAN Data Portal lookup fills rows for you.
sourceRefs:
  - backend/src/modules/external_data/application/use_cases/bought_item_import/batch_create_items.py
  - backend/src/modules/external_data/application/use_cases/bought_item_import/_import_rows.py
  - backend/src/modules/catalogue/domain/services/data_import_profiles.py
  - backend/src/modules/catalogue/domain/policies/order_code.py
  - frontend/src/shared/spreadsheet-import/components/SpreadsheetColumnNamesButton.vue
lastVerified: 2026-11-10
---

**Import from file** on the bought items catalogue creates one bought item per row of an Excel sheet. You upload the file, review every row, and the create button, for example **Create 3 items**, makes the items that are ready. Nothing is created before that.

## Preparing the file

The sheet needs a header row with one column per field. Glados finds the header on its own and recognises the column names an administrator set under Settings, Data import, in English or German. **Column Names** shows every name it recognises for each field. When a required column is not recognised, you choose the column for each field yourself for this upload.

Without the lookup every row needs an **Article name**, an **Order code** and a **Manufacturer**. The manufacturer must be the name of an existing supplier, in any upper or lower case. Everything else is optional. **Article groups** may hold several names separated by a semicolon or a comma, each in any language the group carries. **Mass (g)** is a whole number of grams. One file holds at most as many rows as the settings allow, 100 unless your administrator changed it.

## Looking up in the EPLAN Data Portal

When the Data Portal is switched on, tick **Look up in the EPLAN Data Portal** before you upload. Then an order code or an EPLAN part number per row is enough. The portal fills the article name, the order codes, the EAN, a link, the manufacturer and the product family, and where your file says something else, the portal wins and the row tells you so. Mass, tariff number and notes still come from the file. A part whose manufacturer has no supplier with its EPLAN Data Portal code is invalid until the code is entered on the supplier.

## Reading the review

Every row shows a status. **Ready** rows will be created. **Exists** means the item is already in the catalogue, found by its GTIN, its EAN or its manufacturer and order code; it is not imported and the row lists where the file differs. **Duplicate** repeats an earlier row. **Unknown reference** names a manufacturer, article group or product family Glados does not know. **Not found** and **Ambiguous** only appear with the lookup: choose the right part, or create the row from the file. **Invalid** says what is missing or why the item could not be created, for example a GTIN another item already has. Edit or remove a row and press **Validate** again.

## Creating the items

The create button makes the ready rows in one go. With the lookup it also links the existing items to their part in the Data Portal. Those rows leave the draft, and the others wait for the next try. While a draft waits, the button on the catalogue shows a badge with "An unfinished import is waiting.", and **Discard draft** throws the rows away.

## Examples

**A plain sheet.** Three Festo cylinders with name, order code and Festo as manufacturer. All three are ready and **Create 3 items** makes them.

**An ambiguous number.** With the lookup, one Siemens order code matches two parts. Choose the right one in the row, validate again, and the row becomes ready.

**An item you already have.** A row's order code is 3RT2015 1BB41 and the catalogue holds 3RT2015-1BB41 from the same manufacturer. The row shows Exists, because case, spaces, dashes, dots, slashes and underscores do not count, and nothing is created.
