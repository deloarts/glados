---
title: Machine Pools
summary: What a machine pool is, which work it can take, and how Auto-Plan and the shop floor use it.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/machine_pool/create_pool.py
  - backend/src/modules/fulfillment/application/use_cases/machine_pool/update_pool.py
  - backend/src/modules/fulfillment/domain/services/machine_pool_rules.py
  - backend/src/modules/fulfillment/application/use_cases/machine_pool/place_pool.py
lastVerified: 2026-11-10
---

A machine pool groups machines that can stand in for each other, such as three similar lathes. You assign an order to the pool instead of a single machine, and it runs on whichever member has time. The list lives under Resources, **Machine Pools**.

## Setting up a pool

**Name** is required, and two pools may share a name, so pick one that tells them apart. **Machines** picks the members. An archived machine can still be picked, with a warning, and a pool may also have no members yet. **Note** is optional.

## Which work a pool takes

A pool can take only the fabrication methods that every member has. If one lathe can also mill and the others cannot, the pool takes turning but not milling. A pool without members takes nothing. Inspection work and manual work never go to a pool: inspection goes to a QA machine, and manual work needs no machine at all.

## How planning uses a pool

Every order of a pool runs on one of its members that has working time. Auto-Plan has a **Planning level**. At **Pools**, the default in the dialog, it keeps an order on its pool and leaves the choice of member open. At **Machines**, it places the order on a member that can do the work.

Pools also appear where you assign a lot, in the production queue, on the machine boards of infoscreens and in the machine filter of the **KPIs**.

## Managing the list

You need the permission **Write Production Machines** to create, edit, archive and restore pools. Without it the buttons show disabled. Nothing blocks archiving a pool. **Show Archived** lists archived pools again. The **Machines** column can filter the list by member. Changing, archiving or restoring a pool replans the schedule.

The order of the list is the order the pickers offer the pools in. If you may edit pools, the first column shows a grip in every row. Hold the grip and drag the row to its new place; a line shows where it will land. The grip shows only while no sort, search or filter is active, since those show the rows in another order. New pools go to the end.

## Examples

**Three lathes.** Create the pool Lathes with your three lathes as **Machines**. A turning order assigned to Lathes runs on whichever lathe has time first.

**A member that can do more.** One of the lathes can also mill. The pool still takes only turning, because milling is not a method of every member. Assign milling work to that lathe directly.

**A lathe leaves.** You archive one lathe. It stays a member until you take it out, and the pool form marks it with a warning, so take it out of **Machines** to keep the pool tidy.
