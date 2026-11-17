---
title: Creating Demands from a Sheet
summary: How Batch Create turns an Excel sheet into many bought or made item demands, how each row finds its item and project, and what the review statuses mean.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/_demand_family/batch_demands.py
  - backend/src/modules/fulfillment/application/services/batch_demand_import.py
  - backend/src/modules/fulfillment/application/use_cases/bought_item_demand/batch_demand_items.py
  - backend/src/modules/fulfillment/application/use_cases/made_item_demand/batch_demand_items.py
  - frontend/src/shared/demand-import/components/DemandImportDialog.vue
  - frontend/src/shared/demand-import/stores/createDemandImportDraftStore.ts
lastVerified: 2026-11-12
---

**Batch Create** on the **Bought Items Demand** and the **Made Items Demand** lists creates one demand per row of an Excel sheet, for example a parts list exported for a project. It needs **Write Demand Items**. The import only looks items and projects up: it never creates a catalogue item or a project, so both must exist before you upload. The other way round, **Export** in the same bar saves a demand list as an Excel file, see [Exporting Demands and Orders](/handbook/procurement/list-export).

## Preparing the sheet

The sheet needs a header row. Drop the file on **Upload Excel File** or click to choose it. **Column Names** lists every column name Glados recognises for each field. When every required column is recognised, the review opens and the rows are validated at once; otherwise you assign the columns by hand and press **Continue**.

A bought item row needs **Project**, **Quantity**, **Unit** and either a **Part Number** or an **Order Code / Partnumber** with its **Manufacturer**. Glados tries the part number first and falls back to the order code and manufacturer. A made item row needs **Project**, **Quantity**, **Part Number** and **Revision**. **Article Name**, **Note** and **Desired Delivery Date** are optional. A quantity in pieces must be a whole number above zero, and a file holds at most as many rows as the data import settings allow.

## Reading the review

**Matched** rows are ready. **Unresolved** means the project number matches no project. **Not found** means no catalogue item has that number, and **Ambiguous** that several do. **Invalid** says what is wrong, for example a missing unit, a project that is not active or an item that can no longer be demanded. A matched row whose article name or other details differ from the catalogue shows **Differs from catalogue**; the demand is still created for the catalogue item and the file's values are never written to it.

You cannot edit a row in place. Remove it with **Remove Row**, enter it again with **Add Row**, and press **Validate**.

## Creating the demands

**Create** is enabled only when every row is matched. Glados checks every row again and creates all demands together, or none when a row fails. Until then the rows stay as a draft in this browser: **Batch Create** shows a badge with "You have an unfinished batch import", and **Discard Draft** throws the rows away.

## Examples

**A clean parts list.** Twelve bought item rows for project 24017, each with a part number. All are matched, and **Create** makes twelve demands.

**A typo in the project.** One row says 24071. It shows **Unresolved**, so you remove it, add it again with the right number and validate.

**A revision that does not exist.** A made item row asks for revision C of a part that only has A and B. It shows **Not found** until the row names an existing revision.
