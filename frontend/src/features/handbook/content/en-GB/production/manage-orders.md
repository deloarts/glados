---
title: Manage Orders
summary: How to hand lot positions to a supplier by putting them on a purchase order, from the lots list or from a single lot.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_lot/assign_external_position.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/record_lot_position_provision.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - frontend/src/features/production/lots/components/LotsListManageOrdersPanel.vue
lastVerified: 2026-11-10
---

Manage Orders is how a production step gets outsourced. You pick one purchase order, click the steps that should go to its supplier across as many lots as you like, and assign them in one go. Each step becomes a line on that order, so the supplier comes from the order. What the step shows afterwards is explained on [Lot Position Status](/handbook/production/lot-position-lifecycle).

## Opening the panel {#order}

Click **Manage Orders** in the controls bar of the Lots tab. The button needs **Write Production Lots** and **Write Orders** and shows disabled with a tooltip without them. Pick the order under **Select an order**, or click **Create New Order**, which fills in the preferred supplier of the first selected step. The **Smart Filter** in the **Filters** menu then shows only lots with something left to outsource.

For a single lot, click **Manage** on the lot page and open **Manage Orders** there, or click **Assign Externally** on a position. That form also asks for **Unit** and **Items per Unit**. The step list offers a third way, described in [Manage Production](/handbook/production/manage-production#step-list).

## Which steps you can click {#steps}

You can click a step whose position has pieces left and no open supplier line, while the lot is still active. An unassigned position becomes External, and one already planned in-house becomes Mixed. A position whose supplier line was closed short can be assigned again for the rest. A warning icon marks a position with no step flagged as typically outsourced, but you can still assign it.

## What you set per row {#fields}

Each row shows the lot number, position, fabrication methods and remaining pieces. **Quantity** starts at all remaining pieces and takes whole pieces from 1 up to that number. **Price**, **Expected Delivery** and **Expected Pickup** are optional, and the price is in the display currency. The line counts in pieces, and you can change it on the order later.

## Assigning {#assign}

**Assign Position** works once an order and at least one step are selected. Each row is assigned on its own. Rows that succeed leave the selection, and rows that fail stay selected with a message naming them. The panel stays open and the list refreshes. An assignment is refused when someone canceled the order or the lot's project is not active.

While the order is a draft or requested, **Write Orders** is enough, and on a partially ordered order too, because the new line is not with the supplier yet. Once the whole order has been ordered, you need **Manage Orders**.

The new line starts as pending, so the step shows **Allocated** until purchasing marks the line ordered.

## Sending material to the supplier {#provisions}

When you send pieces to the supplier, click **Record Provision** on an External or Mixed position after clicking **Manage** on the lot page, and enter **Quantity**, **Date** and an optional **Note**. You cannot record more than the previous step has made available. This needs **Write Production Lots**.

## Undoing an assignment {#undo}

Click **Unassign** on the position, or delete the line from the order. Both work only while the line is pending or requested and no provision was recorded. The position falls back to Internal when in-house work remains, otherwise to Unassigned.

## Examples {#examples}

You assign 30 of 100 pieces of a milling step to a supplier. The step shows **Allocated**, and the other 70 stay free for Manage Production.

You assign three steps in one go and one fails because its lot's project is no longer active. Two lines are created and the failed row stays selected.
