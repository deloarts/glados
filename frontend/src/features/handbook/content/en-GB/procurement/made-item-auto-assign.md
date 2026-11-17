---
title: Auto-Assigning Lots
summary: How Auto-Assign turns every made item demand that still lacks coverage into lots, one per project and item, and how Manage Lots does the same for the demands you pick.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_lot/auto_assign_lots.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/create_lot.py
  - frontend/src/features/production/made-item-demands/components/MadeItemsAutoAssignLotsDialog.vue
  - frontend/src/features/production/made-item-demands/components/MadeItemsDemandsManageLots.vue
lastVerified: 2026-11-10
---

A made item demand is covered by a production lot, and creating the lot is what allocates the demand. **Auto-Assign** on the **Made Items Demand** list does this for every demand at once, while **Manage Lots** does it for the demands you select. Both buttons appear only when production planning is switched on, and both need **Write Production Lots**; without it they show disabled. What a lot then goes through is described in [Lot Lifecycle](/handbook/production/lot-lifecycle).

## What Auto-Assign proposes

**Auto-Assign** opens **Auto-Assign Lots** with a preview and changes nothing yet. It takes every made item demand that is Open or Allocated and still has an uncovered rest, and groups the demands by project and item. Each group becomes one lot. The **Lot Quantity** is the sum of the rests, so a lot matches its demands one to one, and **Required Delivery** is the earliest desired delivery date among them. A group with a high priority demand is marked **High**, and a group of several demands lists them under **Contributing Demands**. Demands of a project that is not active, and of an item that can no longer be demanded, are left out. When nothing is left to cover, the dialog says "No unallocated demand to assign." **Create Lots** creates all lots of the preview together.

## Picking the demands yourself

**Manage Lots** opens a panel next to the table. Select demands in the table, and the panel groups them by project and item like the preview. You can change a lot's quantity, priority and required delivery date, set **Overwrite Priority (all)** or **Overwrite Required Delivery Date (all)** for every row, and take a demand out with **Remove from group**. A larger lot quantity leaves the extra pieces unallocated, and a smaller one gives the later demands less. **Create Lots** creates the lots shown.

## Examples

**The normal case.** Project 24017 has two Open demands for the same bracket, 8 and 4 pieces. The preview shows one lot of 12 with both under **Contributing Demands**.

**Two projects.** The same bracket is also demanded by project 24020. It gets a lot of its own, because lots never mix projects.

**A spare piece.** In **Manage Lots** you raise the lot of 12 to 13. Both demands keep their pieces, and the thirteenth is made as a spare.
