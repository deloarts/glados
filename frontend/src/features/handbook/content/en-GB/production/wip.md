---
title: Work in Progress
summary: What the WIP tab lists, how it counts the pieces still raw, between steps and finished, and how to filter it.
sourceRefs:
  - frontend/src/features/production/wip/views/ProductionWipView.vue
  - frontend/src/features/production/wip/components/ProductionWipTable.vue
  - backend/src/modules/fulfillment/application/use_cases/production_order/get_production_wip.py
  - backend/src/modules/fulfillment/domain/services/production_wip_service.py
lastVerified: 2026-11-10
---

The **WIP** tab under Production shows where the pieces of every lot in production are right now. It lists the lots that are **Partially Planned**, **Planned**, **In Progress** or **On Hold**, so drafts and finished or canceled lots stay out. The list only reads, and you change nothing here.

## What a row tells you {#row}

Each row is one lot with its **Lot Number**, the **Item** with its picture and part number, its **Status** and its **Priority**. **Raw / Waiting** counts the pieces the first step has not completed yet, which is the lot quantity minus what the first step completed. **Finished** counts the pieces the last step has completed. The pieces in between are somewhere along the chain.

Open the arrow at the start of a row to see the lot's steps. Each step shows its **Pos.**, its **Kind**, its **Status**, the completed pieces against its quantity under **Qty**, and under **Machine / Supplier** the machines its orders run on or the supplier of an external step. The pieces completed by one step but not yet by the next are waiting at that next step.

Click a row to open the lot.

## Filtering {#filters}

The fields under the headers filter the list as you type. **Lot Number** and **Item** search for text, **Status** and **Priority** offer the values that occur in the list, and **Raw / Waiting** and **Finished** take a minimum and a maximum in two small fields. **Clear** resets every filter.

## Staying current {#refresh}

The list refreshes by itself whenever a lot, a production order or a machine changes, so it can stay open on a screen. The tag on the bar shows **Auto-refreshing** while it loads and the time of the last update afterwards. **Sync** loads it again by hand, and if a refresh fails, the rows stay and the time shows how old they are.

## Examples {#examples}

A lot of 20 pieces has three internal steps. Step 1 has completed 20, step 2 has completed 12 and step 3 has completed 5. The row shows 0 under **Raw / Waiting** and 5 under **Finished**. Of the 15 pieces in between, 8 are at step 2 and 7 are at step 3.

A lot waits for its raw material and no step has completed anything yet. **Raw / Waiting** shows the whole lot quantity and **Finished** shows 0.

A planner sets the **Raw / Waiting** filter to a minimum of 1 and the **Status** filter to **In Progress** to see the running lots that still have pieces left to start.
