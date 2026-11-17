---
title: How Auto-Plan places orders
summary: Which orders Auto-Plan may move, in which order it considers them and which machine or pool each one lands on.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/auto_plan.py
  - backend/src/modules/fulfillment/domain/services/scheduling/candidate_ordering.py
  - backend/src/modules/fulfillment/domain/services/scheduling/machine_selection.py
lastVerified: 2026-11-10
---

[Auto-Plan](/handbook/production/auto-plan) works through the queued orders one at a time. Each order it places takes the earliest free time it can get, so the order in which it considers them decides who gets the early slots. Everything it may not move stays where it is and becomes a fixed point that the rest is planned around. The dates themselves come from the rules on [When an order can start](/handbook/production/auto-plan-timing).

## Which orders may move {#scope}

Only queued orders move. Orders in progress, paused, completed or canceled never do. A pinned order stays where it is unless **Allow overwriting user-planned dates** is on, and a pinned order that the run does move loses its pin. With **Exclude today's planned items** on, an order whose window touches today stays put too, even when it has not started yet.

Orders on machines you did not tick under **Machines to include** keep their plan. An order without a machine is left alone when only unticked machines could take it, so a run for one team does not take work from another. Auto-Plan also moves orders that start within the **Frozen Window (hours)** from the production settings, which a normal recalculation would keep where they are. Manual steps are not part of the run, because they need no machine.

The orders that stay keep their queue places, and the moved orders are appended behind them, never squeezed in between.

## In which order {#ordering}

A lot's target date belongs to its last step. Each earlier step is due when the next one has to start, counted back by a rough lead time. An internal step counts its estimated minutes in whole working days of eight hours, at least one. An external step counts the supplier's lead time, or the lead time of its fabrication methods, or the **Default External Lead Time (days)**. A lot without a target date gives its steps no due date, and those sort last wherever the algorithm sorts by due date.

The algorithm then sorts the orders, and creation order breaks every tie. Whatever the algorithm, the steps of one lot keep their order, so a later step is never placed ahead of its own previous step.

## Which machine {#eligibility}

A machine qualifies only when it covers every fabrication method the order needs. With **Allow assigning machines** off, the order stays on its own machine and only its queue place changes. With it on, every ticked machine that covers the order qualifies. Most algorithms pick the machine that finishes the order soonest. **Balanced Load** picks the machine with the fewest booked minutes so far. Each choice sees everything placed before it, so the run makes the best choice for each order in turn rather than searching for the best plan overall.

## Examples {#examples}

A lot is due on Friday and has two internal steps of six hours each. The last step is due on Friday, so the first step is due on Thursday, and with **Urgent First** that first step is considered before an order of the same urgency that is due next week.

A machine has a pinned order in the middle of its queue and two queued orders behind it. With **Allow overwriting user-planned dates** off, the pinned order stays where it is and both queued orders are placed behind it, in the order the algorithm gives them.
