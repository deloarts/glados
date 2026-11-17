---
title: Manage Production
summary: How to commit lot positions to in-house production on a machine or a machine pool, and where the concrete machine is chosen.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_order/assign_internal_position.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/reassign_production_order_machine.py
  - backend/src/modules/fulfillment/domain/services/production_order_rules.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
lastVerified: 2026-11-10
---

Manage Production commits lot positions to in-house work. Click **Manage Production** on the Lots tab to work through steps across many lots. On a single lot, click **Manage** and open **Manage Production**, or click **Assign Internally** on a position to open **Assign Position Internally**. Each assignment creates queued production orders for the shop floor. **Manage Production** needs **Write Production Lots** and **Write Production Orders**, because assigning creates production orders, and shows disabled with a tooltip naming the one you lack.

## The common flow {#flow}

A position that needs a machine is committed to a machine or, more often, to a machine pool. The pool's queue then gets real dates from the calendars of its machines. The concrete machine is chosen at the latest when the order is started.

## Committing a position {#commit}

Pick a machine or pool under **Machine or pool**, and every selected row goes there. With the **Smart Filter** on, picking one also narrows the list to lots it can make. If you pick nothing, each row goes to its best fitting pool, shown next to the row, and a banner says so before you click **Assign**. A row that no pool can make is disabled, and its tooltip names the fabrication methods nobody covers. A position whose steps are all manual takes **Queue without a machine**, and an inspection position goes only to a QA machine.

**Quantity** takes whole pieces up to the remaining quantity. On the Lots tab, archived machines and pools are not offered, because they take no new orders. On a single lot they are listed last, but they take no new orders either. In **Assign Position Internally** you can split a position over several machines with **Add Machine**, each with its own **Quantity**, while **Assigned** and **Remaining** show what is left. Positions whose production order still has no machine are listed under **Needs a Machine**.

## From the step list {#step-list}

After clicking **Manage** on the lot page, the **Machine / Order** column of the step list assigns one position at a time. For an unassigned position it offers capable machines and pools, open purchase orders, **Create order…** and, for manual positions, **Queue without machine**. A pick commits all remaining pieces, and a purchase order line is counted in pieces with no price or dates. For a queued or paused order the same column changes its machine or pool, unless the order is pinned. Picks wait until you click **Save**. Only a new purchase order is created straight away.

## Resolving the machine {#resolve}

A pool order shows a pool tag until it has a machine, which is chosen in one of four ways. The **Start Production Order** dialog asks for the **Machine**, and on a shared account also for the **Operator**. You can drag the card to a machine column on the [queue board](/handbook/production/queue), pick a machine in the step list, or run [Auto-Plan](/handbook/production/auto-plan) at the **Machines** level.

An order can start only while its lot is not on hold and pieces are available from the previous step or the raw material.

## Orders without a machine {#no-machine}

An order that needs a machine but has neither machine nor pool gets no dates. It sits in the **No Machine Assigned** column of the queue board with a warning until someone assigns it, for example from **Needs a Machine**.

## Examples {#examples}

A position of 20 pieces is split in **Assign Position Internally**, with 12 on one lathe and 8 on another. Two queued orders are created, one per machine.

A milling position goes to the milling pool. On its day the operator clicks **Start**, picks the free machine and the order runs there.
