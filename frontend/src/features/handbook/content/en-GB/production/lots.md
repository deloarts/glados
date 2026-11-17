---
title: Lots
summary: How to create, find and edit production lots on the Lots tab, and what the lot page shows and lets you do.
sourceRefs:
  - frontend/src/features/production/lots/views/ProductionLotsListView.vue
  - frontend/src/features/production/lots/components/LotsControls.vue
  - frontend/src/features/production/lots/components/LotsViewsBar.vue
  - frontend/src/features/production/lots/views/LotDetailView.vue
  - frontend/src/features/production/lots/components/lot-detail/LotDetailRecordGrid.vue
  - backend/src/modules/fulfillment/application/use_cases/production_lot/create_lot.py
lastVerified: 2026-11-10
---

A lot makes one made item in a set quantity for one project, along a route of positions. The **Lots** tab under Production lists every lot. A click opens a lot in a dialog, and **Open Lot** in its header opens the lot's own page.

## Creating and editing lots {#create}

**New Lot** asks for the **Made Item**, the **Project** and the **Quantity**. **Priority**, **Note** and **Required Delivery Date** are optional, and a date set here wins over the one taken from a demand. The lot copies the item's route and material source. Without a material source the lot is still created, but its first in-house step waits for one, see [Material Source](/handbook/production/material-source).

**Edit** opens a panel for the lots you select. It sets **Priority** and **Required Delivery** for all of them, or moves one step: pick the **Step to reschedule** and give a **Planned Start**. Lots without that step are skipped. Both buttons need **Write Production Lots** and show disabled with a tooltip without it.

The four Manage buttons open a panel beside the table, explained in [Manage Orders](/handbook/production/manage-orders), [Manage Quotes](/handbook/production/manage-quotes), [Manage Production](/handbook/production/manage-production) and [Material Source](/handbook/production/material-source). A Manage button shows disabled with a tooltip naming the permission you lack.

## Finding lots {#views}

**Timeline** shows the lots as bars over time. **Column Mode**, the default, gives each step of a lot its own row, **Simple Mode** puts all steps into one cell, and **Widescreen Mode** gives each step its own columns. Grouping by status, priority or project switches to Widescreen Mode. **Hide Completed**, **Hide Canceled**, **Needs Assignment** and **Needs Approval** narrow the list. **Smart Filter** is on by default and, while a Manage panel is open, shows only lots with something left to do there. On a narrow screen the modes and these filters fold into two buttons, and **Filters** counts the ones that are on.

In the filter row, the item and source columns search their two lines separately, and quantity, setup and per piece take a minimum and a maximum.

## The lot page {#lot}

The top bar shows the lot number, its status and tags such as **Waiting on raw material**, **Awaiting QA** or **Late**. The tabs on the right are **Execution** with positions, production orders and completions, **Source & Demand** with the raw material, its demand and receipts, **Piece Balance** with where every piece went, **Project** and **Audit Trail**.

The buttons above print the docket, the label, the scrap tag or the inspection report, and offer **Manage**, **Put on Hold**, **Resume**, **Scrap Pieces**, **Complete Lot** and **Cancel Lot**, explained in [Lot Lifecycle](/handbook/production/lot-lifecycle). **Manage** needs **Write Production Lots** and opens the material source, the steps, the position grouping and the position panels. Ending a lot also needs **Manage Production Lots**, and **Scrap Pieces** needs **Write Production Orders**. A button shows disabled with a tooltip naming the permission you lack.

## On a phone {#phone}

A phone lists each lot with its item, status and required delivery. A tapped lot opens its page, where the actions sit in one **Actions** menu. The Manage panels are left out.

## Examples

A customer needs 40 brackets. Click **New Lot**, pick the made item and the project, enter 40 and save. The lot appears in the list, and its positions wait to be assigned.

Purchasing asks which lots wait for a material decision. Turn on **Needs Approval** and approve or reject each source.

Three lots need their second step a week later. Select them, click **Edit**, choose step 2 as **Step to reschedule** and enter the new **Planned Start**.
