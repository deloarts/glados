---
title: Capacity
summary: How the Capacity tab lays the production schedule out as booked and available hours per day, one row per machine and one per pool, and what a red, empty or Unresolved cell means.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/get_schedule_board.py
  - backend/src/modules/fulfillment/domain/services/scheduling/capacity.py
  - backend/src/modules/fulfillment/domain/services/scheduling/machine_calendar.py
  - backend/src/modules/fulfillment/domain/services/scheduling/forward_walk.py
  - frontend/src/features/production/utils/capacityUtilization.ts
lastVerified: 2026-11-26
---

The Capacity tab shows the same production schedule as the queue board, read a different way. Instead of one card per order, it shows booked and available hours per day, so you can see at a glance which machines and pools have room and which are stretched. Pick the days with **Date range**, and start [Auto-Plan](/handbook/production/auto-plan) from the **Auto-Plan** button in the same bar.

## The two grids {#grids}

**Machines** comes first, with one row per machine. The **No Assignment** row below them collects the orders without a machine: manual steps, orders that have neither machine nor pool, and orders of a pool without members. **Machine Pools** follows, with one row per pool. A pool row only adds up what its member machines carry for it, because a pool is never a resource of its own.

Click the number in a row's **Orders** column to see every order counted in that row over the whole date range. The dialog lists **Order**, **Lot**, **Project**, **Item**, **Step**, **Window** and **Conflicts**.

## Booked, available, overbooked {#minutes}

Each day cell shows the booked hours against the available hours. The available hours come from the machine's working calendar: its own working week or the default one, its date exceptions, holidays and plant shutdowns, and its downtimes. A night shift counts for the day it starts. A cell is orange from 70 percent of the available time and red above 100 percent, and hovering a red cell shows how far over it is. Past days and days without working time are greyed, and today is highlighted.

A machine's row counts every order on that machine, plus every pool order the schedule currently places on it. A pool row is the sum of what its members carry for it, so if a pool row is red, at least one member is red too.

## Unresolved orders {#unresolved}

A pool order that has no machine yet shows an **Unresolved** tag next to its window in the orders dialog. Its dates are real, but the member machine it is counted on is only a forecast. Hovering the tag names that machine when there is one. The machine is fixed when the order is started or by one of the other ways described in [Manage Production](/handbook/production/manage-production#resolve).

## When the board is catching up {#stale}

After a change that moves planned dates, Glados works the new dates into every order in the background. Until that has finished, a banner says that changes since a given time are still being worked into the stored planned dates. The board itself is already up to date. The banner goes away once every stored date has caught up.

## Why is a slot free? {#free-slots}

A free day is not first come, first served. Each machine's queue is planned in its fixed order, and every order starts at the earliest point its own turn allows, so a later order never jumps into a gap an earlier one left. A gap also stays empty when the next order waits for its previous step, for a delivery plus the response time, or for its raw material, or when an order within the frozen planning window keeps its place. The rules are on [When an order can start](/handbook/production/auto-plan-timing).

For example, a lathe shows Wednesday free although an order is queued on it. Its previous step, a hardening step at a supplier, is expected back on Wednesday, and with one day of response time the turning order cannot start before Thursday.
