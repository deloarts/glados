---
title: Exporting the Catalogue
summary: How Export saves the bought or made items list as an Excel file, which rows and columns the file holds, and what happens with a very long list.
sourceRefs:
  - frontend/src/shared/spreadsheet-export/components/SpreadsheetExportButton.vue
  - frontend/src/shared/spreadsheet-export/composables/useSpreadsheetExport.ts
  - frontend/src/shared/spreadsheet-export/utils/fetchExportRows.ts
  - frontend/src/features/bought-items/utils/boughtItemsCatalogueExport.ts
  - frontend/src/features/made-items/utils/madeItemsCatalogueExport.ts
lastVerified: 2026-11-12
---

**Export** in the bar above the bought items and the made items list saves the list as an Excel file. The file holds what you see: the rows your search and filters leave, in the order you sorted them, with the columns you show. Everyone who can open the list can export it, and the file downloads like any other.

## Which rows the file holds

A click on **Export** saves every row of the current filter, not just the page on screen. Your search, the column filters, the sort, **Show Archived** and, for made items, **Show All Revisions** all count. The arrow beside the button offers **All Filtered Rows** and **Selected Rows**. **Selected Rows** saves only the rows you ticked, which is handy for a short list you put together by hand. Ticking rows needs **Write Bought Items** or **Write Made Items**. Grouping does not carry over, the file is always one flat list.

## Which columns the file holds

The file has the columns the list shows, in the same order, so **Columns** in the views bar decides what goes in. Each value keeps its type. Dates are real dates you can sort and filter in Excel, quantities are numbers, and part numbers, order codes and GTINs stay text, so their leading zeros survive. Status and data source show their labels, and groups and product families their names. Next to **Created** and **Changed** the file adds who created or last changed the item. The last column, **Link**, opens the item's page in Glados, which is also where its pictures and files are, since a spreadsheet cannot hold them. The made items list leaves out its picture and files columns for that reason, and the bought items list counts the PDF files.

## Long lists

Up to 5,000 rows the file downloads right away. Above that Glados asks first, because reading the rows takes a moment. While it reads, the button shows how far it got, and **Cancel** stops it without downloading anything. Above 50,000 rows Glados does not start and asks you to narrow the filter.

## Examples

**A list for a supplier.** You filter the bought items by the manufacturer, show the order codes and click **Export**. You send the supplier a sheet with one line per part, and the **Link** column brings you back to each part.

**A handful of parts.** You tick six made items in the list and choose **Selected Rows**. The file holds those six, without reading the rest of the list.

**The whole catalogue.** The list shows 12,430 bought items. Glados asks before it starts, you confirm, and the download follows once all rows are read.
