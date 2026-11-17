---
title: Made Items
summary: What the made items catalogue holds, how revisions work, and which fields of an item come from PDM and which you edit on the web.
sourceRefs:
  - frontend/src/features/made-items/components/MadeItemsCatalogueControls.vue
  - frontend/src/features/made-items/composables/useMadeItemsCatalogueActions.ts
  - frontend/src/features/made-items/components/MadeItemDetailDialog.vue
  - frontend/src/features/catalogue/views/MadeItemDetailView.vue
  - backend/src/modules/catalogue/domain/policies/item_field_ownership.py
  - backend/src/modules/catalogue/domain/policies/pdm_ownership.py
lastVerified: 2026-11-12
---

The made items catalogue lists the parts your workshop makes itself. Every revision of a part is its own row, so a demand or a lot always names the exact revision it builds. The list is the **Made Items** tab of the catalogue and shows the newest revision of each part; **Show All Revisions** lists the older ones too. A click on a row opens the item's page, where a selector next to the part number switches between its revisions.

## Working in the list

**New** creates an item, unless your numbering settings leave made items to PDM. **Edit** switches the list into edit mode for changing several items at once. **Export** saves the filtered list as an Excel file, see [Exporting the Catalogue](/handbook/catalogue/catalogue-export). The row menu offers **Edit**, **Copy**, **New Revision**, **Merge**, **Archive** or **Restore**, **Add to Demand**, **Order / Processing History**, **Print Label** and **Show Changelog**. Editing, copying and new revisions need **Write Made Items**, merging and archiving need **Archive Made Items**.

## The item page

The page shows the item, its **Processes** with the routing, its **Material Source**, its **Demands**, **Orders** and **Lots**, its **Files**, where it is **Used in**, and its **Changelog**. From the top you can **Edit item**, **Create demand**, which needs **Write Demand Items**, and **Print** a label or a docket. **Add to order** stays disabled, because a made item is ordered from a lot's step list.

## Fields from PDM and fields from the web

An item modelled in SolidWorks shows **PDM** as its **Data Source**. Its part number, revision, revision date and revision note come from PDM. Its article name, material, mass, base size, note, weblink, article groups, customer data, process routing and material source are written in the SolidWorks file and arrive with each released version. Its status follows the PDM workflow. While your administrator keeps PDM items read only, these fields show locked with "Managed by PDM", so you change them in the file. One exception is a source item as material source: you can change it on the web, and your choice stays until the engineer sets a different one in the file. The successor, the files and uploaded photos stay yours to edit.

An item created on the web shows **Web**, and you edit everything here. By default some fields, such as the material, are changed only by **New Revision**, which creates the next revision with your values and asks **What happens to the current revision?**: **Replaced**, **Inactive** or **Active**. Only the newest revision is edited; on an older one only the status can change. For an item from PDM, **New Revision** shows disabled, because its revisions come from PDM.

## Examples

**A web item gets a new material.** The material field is locked in the edit dialog. **New Revision** creates revision B with the new material, and revision A is set to **Replaced**.

**An item from PDM.** The article name is locked with "Managed by PDM". The engineer corrects it in the SolidWorks file, and the next release brings it in.

**A different bar for a PDM item.** You pick another source item as its material source on the web. It stays until the engineer sets a different one in the file.
