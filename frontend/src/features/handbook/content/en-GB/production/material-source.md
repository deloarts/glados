---
title: Material Source
summary: How a lot's raw material is chosen, changed for one lot or many, switched after it was ordered, and approved or rejected before it is demanded.
sourceRefs:
  - frontend/src/features/production/lots/components/LotMaterialSourceDialog.vue
  - frontend/src/features/production/lots/components/LotsListManageSourcePanel.vue
  - frontend/src/features/production/lots/components/LotRejectSourceDialog.vue
  - backend/src/modules/fulfillment/application/use_cases/production_lot/switch_lot_material_source.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/approve_lot_source.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/reject_lot_source.py
lastVerified: 2026-11-10
---

A lot's material source is what its first in-house step is made from: a source item such as a raw block, a bought item, or an existing made item that is reworked. A new lot copies the source of its made item. A source item or bought item gives the lot a raw material demand, which purchasing covers under **Source Items Demand**, see [Source Item Demand Lifecycle](/handbook/procurement/source-item-demand-lifecycle). A reworked made item gets no demand. Until a lot has a source, approved where approval is required, its first in-house step is not planned.

## Changing the source of one lot {#change}

On the lot page, click **Manage** and **Change material source**, or right click a lot in the table and pick **Add Source Item**. The dialog **Change Material Source** offers **Source Item**, **Create Source Item**, **Bought Item** and **Made Item**, and saves with **Apply** or **Create and Apply**. **Demand Source Item** creates the raw material demand by hand when a lot has a source but no demand. Changing the source needs **Write Production Lots**, and the button shows disabled with a tooltip without it.

## Changing many lots at once {#batch}

**Manage Source** on the Lots tab opens a panel. Select the lots in the table, pick the **Source Material** and click **Apply Source**. Finished lots and lots whose material has all arrived are skipped and counted. Lots that already have a demand are listed in one question first.

## When the material is already ordered {#ordered}

An open demand nobody has acted on is canceled and replaced after **Replace Source Item Demand** asks you. When the demand is already allocated or ordered, **Switch an Ordered Material** shows how much is allocated and how much has arrived. What arrived stays with the lot, and the old demand is settled with it. Allocations on order lines whose pieces have not arrived are released, so purchasing can cancel those lines or close them short, and the new source is demanded for the missing rest. Once all raw material has arrived, or the lot is finished, the source can no longer change.

## Approving a source {#approval}

With **Require Source Item Approval** on under System Settings, Production, a lot sourced from a source item gets no demand until someone approves it. It shows **Approval Required**, and the filter **Needs Approval** lists these lots. **Approve** and **Reject** sit on the lot's **Source & Demand** tab and in the lots table. Both need **Manage Production Lots** and show disabled with a tooltip without it. Approving creates the demand, and after a switch away from an ordered material it covers only the missing rest, as the switch would without approval. Rejecting asks for a **Reason**, and the lot stays **Rejected** until someone approves it after all or the source is switched. A switch starts a new approval for the new source. Bought items never need approval. Turning the setting off releases the waiting lots, but rejected lots stay rejected.

**Assign Approved Material to Item** also writes the approved source item to the lot's made item, so future lots start with it. It changes an item that names another source item only when **Overwrite Existing Upon Approval** is on, and never replaces a bought item.

## Examples

A lot of 20 brackets is sourced from a raw block while approval is required. A planner clicks **Approve**, and a demand of 20 pcs appears for purchasing.

20 pcs of the wrong steel were ordered and 8 have arrived. Switch the source: the 8 stay with the lot, the new source is demanded for 12, and purchasing settles the old line with the supplier.

A source is rejected because the alloy is wrong. The planner picks another source item, and the lot waits for approval again.
