---
title: When an order can start
summary: How the planned window of a production order is worked out from its previous step, its material, the machine queue and the machine calendar.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/scheduling/forward_walk.py
  - backend/src/modules/fulfillment/domain/services/scheduling/machine_calendar.py
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/auto_plan.py
lastVerified: 2026-11-10
---

Every production order on a queue gets a planned window, its start and its end. Glados works these windows out again whenever something changes that can move them, and [Auto-Plan](/handbook/production/auto-plan) uses the same rules after it has placed its orders. This page explains what holds an order back and how its working time is spread over the calendar.

## What an order waits for {#waits}

An order starts at the latest of four moments. The first is its own **Not before** date, when a planner set one. The second is the end of its previous step. An internal step is ready on the day its last order is planned to end. An external step is ready on its delivery day, or else on its ready for pickup date, or else on its expected delivery date. The third, for the first step only, is the arrival of the raw material. The fourth is the end of the work already queued in front of it on the same machine.

The **Response time for planned start (days)** is added to the end of the previous step and to the material's arrival before they are compared, because a step finished today does not mean the next one can start today too. A queued order never starts before now.

An order stays without dates when an earlier step has no date at all, or when its raw material has neither arrived nor been ordered with a delivery date. It gets dates once pieces are already waiting at its step.

## Working time {#calendar}

From its start, the order uses up its estimated time on the machine's working calendar. That is the machine's own working week when it has one, otherwise the default working week, with any date exceptions of the machine on top. Holidays and plant shutdowns entered under **Holidays** in **Resources** close every machine unless the machine's own exception opens it that day. Downtimes are cut out of the calendar, and a machine that is down when Auto-Plan starts is left out of that run. Days without working time are skipped, so a long job spills over into the next working days. Hours are plant time, and a night shift that runs past midnight counts for the day it starts.

Manual steps need no machine and use the default working week. A machine whose calendar holds no working time at all, such as a week of zero hours, gets no dates for its orders, which are flagged.

## Orders that keep their window {#kept}

A running order stays at the moment it last started or resumed. A paused order uses no time. A pinned order keeps its window, and so does a queued order that starts within the **Frozen Window (hours)**, unless Auto-Plan or a planner moves it. The order after a kept window still starts after the order before it, and a kept window that overlaps its neighbour is flagged.

## Examples {#examples}

The first step of a lot ends on Tuesday afternoon and the response time is one day. The second step can start on Wednesday, so on a free machine it starts at the first working hour on Wednesday.

The raw material of a lot is ordered with a delivery date of the 12th. Its first step can start on the 13th with a response time of one day. If the material had no delivery date, the first step would stay without dates until someone orders it with one.
