---
title: Source Items
summary: What a source item is, how its type, dimension and material describe the raw material, and how lots, demands and orders use it.
sourceRefs:
  - frontend/src/features/source-items/components/SourceItemsCatalogueControls.vue
  - frontend/src/features/source-items/components/SourceItemCreateForm.vue
  - frontend/src/features/source-items/components/SourceItemsCatalogueTable.vue
  - frontend/src/features/catalogue/views/SourceItemDetailView.vue
  - backend/src/modules/catalogue/domain/policies/catalogue_item_status.py
lastVerified: 2026-11-10
---

A source item describes the raw material a made item starts from, for example a steel bar 40 mm round in 1.0037 or an aluminium plate. A made item names it as its material source, and every lot of that item then demands it, see [Source Item Demand Lifecycle](/handbook/procurement/source-item-demand-lifecycle). The list is the **Source Items** tab of the catalogue. Source items belong to Glados alone, so PDM never changes them, although the SolidWorks add-in can create one too.

## Creating a source item

**New** opens **Create Source Item**. Choose the **Type**, describe the **Dimension** by its shape, **Block**, **Profile**, **Turned Part**, **Tube** or **Custom**, and enter the **Material**. **Mass [g]**, **Manufacturer**, **Order Code 1**, **Order Code 2** and **Note** are optional. **Similar Items** shows existing items with the same type and material while you type, so you can reuse one instead. An item with the same type, dimension and material as an existing one is refused, and the dialog offers to edit the existing item. The types themselves are kept under resources, see [Source Item Types](/handbook/resources/source-item-types).

You can also create a source item while choosing a made item's material source: the selector offers **Create Source Item**, and when an identical one exists, it is used instead.

## Working in the list and on the page

**Edit** switches the list into edit mode for changing several items at once. The row menu offers **Edit**, **Print Label**, **Archive** or **Restore** and **Copy UUID**. Editing needs **Write Source Items**, archiving **Archive Source Items**, and without them the actions show disabled.

The item page shows the item, its **Files**, the **Orders** and **Demands** that name it with their lots, where it is **Used in**, and its **Changelog**. **Create demand** and **Add to order** stay disabled there, because a source item demand is created from a lot's material source and the material is ordered from its demands.

## Status

A source item is **Active**, **Inactive** or **Replaced**, like every catalogue item, and only an active one can be chosen as a new material source or demanded. A replaced item names its **Successor Item**, see [Catalogue Item Lifecycle](/handbook/catalogue/catalogue-item-lifecycle).

## Examples

**A new bar.** You create type Round bar, a **Turned Part** of 40 mm diameter and 3000 mm length, material 1.0037. It is ready to be chosen as a material source.

**The same bar again.** A colleague enters the same type, dimension and material. Creation is refused, and **Edit existing item** opens the one you made.

**A material that is no longer bought.** You set the old bar to **Replaced** and name the new one as its successor. The old bar can no longer be chosen for new work, while lots that already use it carry on.
