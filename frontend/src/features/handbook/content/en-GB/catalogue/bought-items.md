---
title: Bought Items
summary: What the bought items catalogue holds, what you can do from its list and from an item's page, and which fields PDM manages once it knows an item.
sourceRefs:
  - frontend/src/features/bought-items/components/BoughtItemsCatalogueControls.vue
  - frontend/src/features/bought-items/composables/useBoughtItemsCatalogueContextMenu.ts
  - frontend/src/features/catalogue/views/BoughtItemDetailView.vue
  - backend/src/modules/catalogue/domain/policies/pdm_ownership.py
  - backend/src/modules/catalogue/domain/policies/catalogue_item_status.py
lastVerified: 2026-11-12
---

The bought items catalogue lists every part you buy from a supplier, such as contactors, cylinders and screws. Each item is one row, found by its manufacturer and order code, and every demand and order line for the part points at it. The list is the **Bought Items** tab of the catalogue, and a click on a row opens the item's own page.

## Working in the list

**New** creates an item in a dialog, where **Fill from the EPLAN Data Portal** can fill the fields for you, see [EPLAN Data Portal](/handbook/catalogue/eplan-data-portal). **Import from file** creates many items from a sheet, see [Importing Bought Items from a File](/handbook/catalogue/bought-item-import). Both are hidden when your numbering settings do not allow creating bought items on the web. **Edit** switches the list into edit mode, where you select several rows and change a field for all of them at once. **Export** saves the filtered list as an Excel file, see [Exporting the Catalogue](/handbook/catalogue/catalogue-export).

The row menu offers **Edit**, **Copy**, **Merge**, **Archive** or **Restore**, **Create Demand**, **Add to Order**, **View Order History**, **Show Changelog** and **Print Label**. **Merge** moves the demands, order lines, article groups and files of one item to another and archives it; use it when the same part was entered twice. Editing and copying need **Write Bought Items**, merging and archiving need **Archive Bought Items**. **PDM Preview** appears when PDM is connected and lists the vault files the catalogue has not caught up with yet.

## The item page

The page shows the item with its pictures and fields, its **Demands**, its **Orders**, its **Files**, where it is **Used in** across projects, and its **Changelog**. From the top you can **Edit item**, **Lookup in Data Portal** when the Data Portal is on, **Create demand**, **Add to order** and **Print** a label or a docket. Each action needs its own permission, **Write Bought Items**, **Write Demand Items**, **Write Orders** or **Print Documents**, and shows disabled without it.

## Status and PDM

An item is **Active**, **Inactive** or **Replaced**, and only an active item can be named on a new demand or order line, see [Catalogue Item Lifecycle](/handbook/catalogue/catalogue-item-lifecycle). An item created on the web shows **Web** as its **Data Source**. When PDM delivers a file that matches it, by its part number, its GTIN or its manufacturer and order code, PDM claims it, and from then on its **Data Source** shows **PDM**. A claimed item keeps that for good. Its article data and its status then come from PDM, the edit dialog shows those fields locked with "Managed by PDM", and you change them in the SolidWorks file. If your administrator lifted that lock, Glados asks before you edit, because PDM may overwrite the change. The product family, the delivery tolerances and the files stay yours to edit.

## Examples

**A new part.** You need a contactor that is not in the catalogue. **New**, a search in the Data Portal and **Save** create it, and **Create demand** on its page asks for it for your project.

**The same part twice.** Someone created the same cylinder again by hand. You **Merge** the duplicate into the original, and its demands and order lines move over.

**A part PDM knows.** An engineer added your web item to an assembly. After the next release its data source shows **PDM**, and its article name can only be changed in the SolidWorks file.
