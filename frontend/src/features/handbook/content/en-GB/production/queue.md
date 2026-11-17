---
title: Queue Board
summary: How the Queue tab lays out the open production orders by machine and day, and how you move, pin, start, pause, split and merge them.
sourceRefs:
  - frontend/src/features/production/queue/components/ProductionQueueBoard.vue
  - frontend/src/features/production/queue/composables/useQueueBoardGroups.ts
  - frontend/src/features/production/queue/components/ProductionOrderCard.vue
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/split_production_order.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/merge_production_orders.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/record_manufacturing_assessment.py
lastVerified: 2026-11-10
---

The **Queue** tab under Production shows every open production order as a card, one column per machine, and updates by itself when someone changes an order.

## Columns and days {#columns}

**Manual Work** holds steps that need no machine and **Inspection** the QA steps, followed by the pools and machines in alphabetical order. **No Machine Assigned** appears only for old orders with neither machine nor pool. Click a machine name to open its [machine page](/handbook/production/machines).

In a column, **In Process** lists the running orders, and the waiting ones follow by planned start day. The date range on the bar starts as today through Sunday and spans up to 31 days. Work planned before the range sits under **Overdue**, and work planned after it stays off the board.

**Show Completed** adds the orders finished in the last seven days under **Completed / Canceled**. **Hide Not-Ready** hides the waiting orders that **Start** would refuse right now, and this browser remembers the switch. **Horizontal** and **Vertical** set the layout.

## Moving and pinning {#pin}

Drag a card by its handle to reorder the queue, or onto another column in the same day to move it there, as long as that machine or pool covers its fabrication methods. Dragging needs **Write Production Orders** and is not offered on a phone.

**Pin to top** fixes an order in place: it cannot be dragged, its dates stay, and Auto-Plan leaves it alone unless **Allow overwriting user-planned dates** is on. Pinning needs **Manage Production Orders**.

## Starting and resuming {#start}

**Start** begins a queued order and **Resume** continues a paused one, normally at once. The **Start Production Order** dialog only opens when a shared shop-floor account has to pick the **Operator** or an order on a pool has to pick its **Machine**. When Start is disabled, its tooltip says why, for example that the step before it has made nothing yet or the lot is on hold.

## Pausing {#pause}

**Pause** interrupts a running order. The **Reason** is optional, and a shared account also picks the **Operator**. An order that paused because its lot went on hold resumes with the lot.

## Splitting {#split}

**Split**, under **More actions**, divides a queued order of more than one piece into two or more parts. Each part takes whole pieces, and **Save** waits until the parts add up to the order's quantity. Every part gets its own setup time and joins the end of the same queue.

## Merging {#merge}

**Merge** joins queued orders of the same lot position on the same machine and pool. Tick the orders and press **Merge**. The order furthest ahead in the queue keeps the total, the others are canceled, and the duration counts one setup again. A merge cannot be undone.

## Completing and canceling {#assessment}

**Complete** opens the dialog described in [Recording Completions](/handbook/production/completions). Once the order is finished, the **Manufacturing Assessment** asks how it really went, to improve future time estimates. **Actual Minutes per Piece** is required, and **Skip** closes it without saving.

**Cancel**, also under More actions, asks you to confirm and then cancels the order. You can cancel an order you created yourself, and an order someone else created needs **Manage Production Orders**. Starting and completing an inspection step also needs **Record QA Inspections**. A button whose permission you lack shows disabled with a tooltip that names the permission, and a menu entry names it when you point at it.

## Examples {#examples}

An order of 40 pieces waits on a pool. The operator presses **Start**, picks the free machine, and the card moves to that machine.

A planner splits an order of 25 pieces into 13 and 12 and drags the second part to another machine.

Two orders of 5 pieces for one position wait on a machine. Merging them leaves one order of 10 with one setup.
