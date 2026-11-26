---
title: External Work
summary: How the External Work list shows which parts go to a supplier for hardening, coating or another outside process, by when they must leave, and how you give them to a supplier.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/external_work/get_external_work.py
  - backend/src/modules/fulfillment/domain/services/scheduling/external_work.py
  - backend/src/modules/fulfillment/domain/services/scheduling/external_work_explanation.py
  - frontend/src/features/procurement/components/ExternalWorkTable.vue
  - frontend/src/features/procurement/composables/useExternalWorkRowMenu.ts
lastVerified: 2026-11-26
---

**External Work** in Procurement lists every part of an open lot that goes to a supplier for an outside process, such as hardening or galvanizing. It tells you when the part can go, by when it must go so the steps after it are not late, and when it comes back, so you can collect parts for one supplier and send them together.

## Which parts appear

A part appears once its lot step is on a supplier's order, or while it waits for a supplier and its fabrication method is marked as usually outsourced. Lots with only internal steps do not appear. Give the outsourced methods a lead time and a default supplier, otherwise their parts get no dates and no suggestion.

## What the dates mean

**Ready From** is when the pieces of the step before are ready, with any wait after that step, or when the raw material is in, plus the response time. A delivery that is late counts as today. **Send By** counts back from the lot's target date: less the safety margin, less the steps after this one with the waits after them, and less the lead time. **Back By** is the supplier's date once the order line has one, else **Send By** plus the lead time. Hover the small line under a date to see how it was counted. The safety margin is **Safety Margin for External Work (days)** in the production settings.

A note in the **Note** column marks a part that cannot be ready by its **Send By** day, one whose **Send By** day has passed, and a lot without a target date.

## Grouping and filtering

**Group by** sorts the page by **Method** or **Supplier**. Each group shows its next send-out day and how many parts are critical. **Only With Supplier** hides the parts nobody ordered yet, **Only Critical** keeps the late ones. Every column has its own filter in the row under the headers.

## Giving a part to a supplier

Right-click a row. **Use Suggestion** puts the part on a draft order of the method's default supplier, the open draft if there is one. **Choose Supplier…** opens the dialog to pick another supplier or order. **Remove From Order** takes it off again until pieces went out, and **Record Provision…** books the pieces you handed over. These entries need **Write Orders**, and the provision **Write Production Lots**; without them they are disabled.

## Examples

**A hardening batch.** Group by **Supplier**: the hardening shop's group says its next send-out is on Tuesday. You right-click each part that is ready and choose **Use Suggestion**, and they all land on one draft order.

**A part that will be late.** **Ready From** says Friday but **Send By** says Thursday, and the note says it is not ready in time. You check the step before it in the lot.
