---
title: Exporting Demands and Orders
summary: How Export saves a demand list or the orders list as an Excel file, which rows and columns it holds, and why an order becomes one row per line.
sourceRefs:
  - frontend/src/shared/components/demands/demandExportColumns.ts
  - frontend/src/features/procurement/utils/boughtItemDemandsExport.ts
  - frontend/src/features/production/made-item-demands/utils/madeItemDemandsExport.ts
  - frontend/src/features/production/source-item-demands/utils/sourceItemDemandsExport.ts
  - frontend/src/features/orders/utils/ordersExport.ts
  - frontend/src/shared/spreadsheet-export/composables/useSpreadsheetExport.ts
lastVerified: 2026-11-12
---

**Export** in the bar above the **Bought Items Demand**, **Made Items Demand**, **Source Items Demand** and **Orders** lists saves the list as an Excel file. Like the catalogue export, see [Exporting the Catalogue](/handbook/catalogue/catalogue-export), the file holds every row your search and filters leave, in the order you sorted them, not just the page on screen. Everyone who can open the list can export it.

## Which demands the file holds

A click on **Export** saves the filtered demands. The arrow beside the button offers **All Filtered Rows** and **Selected Rows**, and **Selected Rows** saves only the demands you picked with a Ctrl-click or the checkboxes. Grouping does not carry over, the file is one flat list.

Each demand is one row with its number, status, bucket, quantity and unit, its project with customer and description, the demanded item, the desired delivery, when and by whom it was created, and its note. The item columns differ per list. Bought item demands show the article name, order code, part number and manufacturer, made item demands the part number, revision and steps, and source item demands the dimension, material, type and lot. The status is the demand's own. The list can show a finer one, such as how much is already ordered, which comes from the allocations, and the file leaves the allocations and orders out. The last column, **Item Link**, opens the demanded item's page.

## How orders become rows

The orders file has one row per order line, so you can filter and add up the lines in Excel. The order's number, status, supplier and order date repeat on each of its lines, and an order without lines still gets a row of its own. Prices are numbers in the currency the column header names. Extra costs and discounts belong to the order, not to a line, so the line totals differ from **Total (net)** when an order has any. The last column, **Link**, opens the order. The orders list has no row selection, so **Export** always saves the filtered orders.

## Long lists

The same limits apply as in the catalogue: above 5,000 rows Glados asks first, and above 50,000 it asks you to narrow the filter. For orders the limits count orders, not lines.

## Examples

**Open demands for one project.** You filter the **Bought Items Demand** list by the project and hide the fulfilled ones, then **Export**. The file lists what is still missing, with the order code to quote.

**A supplier's open lines.** You filter **Orders** by the supplier and **Hide Delivered**, then **Export**. Each open line is a row with its quantity, price and expected delivery.
