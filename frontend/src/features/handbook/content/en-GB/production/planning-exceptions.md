---
title: Planning Exceptions
summary: What the Exceptions tab lists, how to read a row, why each kind appears and when it goes away again.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_lot/get_planning_exceptions.py
  - backend/src/modules/fulfillment/domain/value_objects/planning_exception_kind.py
  - frontend/src/features/production/exceptions/components/PlanningExceptionsTable.vue
  - backend/src/modules/fulfillment/application/use_cases/production_lot/notifications.py
lastVerified: 2026-11-10
---

The **Exceptions** tab under Production lists what needs a planning decision: demands that are short again, lots that ended short, lots whose raw material is not secured and lots that are late. Each row names the problem and links to what caused it, but the list fixes nothing by itself. The bar **Planning Exceptions** above the list shows how many exceptions there are, with one tag per kind. Rows are sorted by kind in the order of the next section, and within a kind the earliest target date or the oldest cause comes first. The list refreshes on its own, and a row disappears as soon as its cause is resolved, for example when the open rest is allocated again or the demand is fulfilled or canceled.

## What appears there {#kinds}

**Lost at receipt** and **Closed short**: a bought item or raw material demand has part of its quantity open again because pieces on its order line were lost at the goods receipt or the line was closed short. Allocate the rest to another line, order it again, or mark the demand fulfilled.

**Lot ended short**: a lot was force-completed below what a made item demand needed. Everyone with **Manage Production Lots** also gets a notification when this happens. Create a new lot for the rest or settle the demand.

**Short of material**: a lot that is partially planned, planned, in progress or on hold, never a draft, whose raw material is partly neither ordered nor taken from stock, or ordered on a line without a delivery date. Its first in-house step cannot be planned in full until the material is covered and dated. The row drops off once the first step has completed all its pieces. A lot without a material source is not listed here, since it waits for its source by design.

**Late**: a lot in the same statuses whose target date has passed or whose production orders are planned to end after it.

## Reading a row {#row}

**Project** shows the project number, which opens the project, and the customer below it.

When pictures are stored, a picture of the item comes next. **Item** shows the part number of a made item, the order code of a bought item or the dimension of a raw material, with the article name or the material below it. Click the first line to open the item. A raw material without a dimension shows its material there instead, and a made item without a part number shows **No part number** with a warning icon.

**Lot, Order Line, Demand** names where the problem arose. The lot number opens the lot, the order line opens its order, and the demand number tells you which demand is short.

**Detail** says in one sentence what is open or how late the lot is, and **Since** says when the cause was recorded. Late lots show no date there, since their delay is in the detail.

## Examples {#examples}

A lot shows **Short of material** with the detail that 2 pcs of raw material are neither ordered nor taken from stock. Open the lot, then order the 2 pcs or take them from stock. The row goes away once it is covered.

A lot shows **Late** with a target of 22 October and a planned end of 11 November. Open the lot and either move its target date or replan its production orders so they end in time.

## Limits {#limits}

Lines with lost pieces or a close short are read from the most recent 500, and force-completed lots from the last 90 days.
