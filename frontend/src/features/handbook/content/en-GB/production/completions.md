---
title: Recording Completions
summary: How to record finished pieces on a production order, how an inspection rejects pieces into rework and replacement lots, and how a mistaken completion is reversed.
sourceRefs:
  - frontend/src/features/production/components/ProductionOrderCompletionDialog.vue
  - frontend/src/features/production/lots/components/lot-detail/ReverseCompletionDialog.vue
  - backend/src/modules/fulfillment/application/use_cases/production_order/record_production_order_completion.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/reverse_production_order_completion.py
lastVerified: 2026-11-10
---

A completion records how many pieces of a production order were finished on a day. **Complete** on the queue board or on a machine's page, the **Complete** button on a step in the lot page's Manage mode and **Record Result** on a QA task all open the dialog **Record Completion**. An order takes completions only while it is **In Progress** and its lot is not on hold. Recording needs **Write Production Orders**, and the buttons show disabled with a tooltip without it.

## Recording pieces {#record}

**Quantity Completed** starts with what the order may still book, its quantity less every piece already processed. Enter less for a partial completion. The order stays **In Progress** and becomes **Completed** once all its pieces are booked. **Completion Date** is today by default and can be neither in the future nor before the order was started. **Operator** appears only on a shared account and must name the member who did the work. **Note** is optional.

A position can only complete what reached it. The first in-house step needs raw material that has arrived, and every later one needs the good pieces of the position before it. Each completion also keeps the machine the order ran on.

## Rejects at an inspection {#rejects}

Only an inspection position rejects pieces, and recording there needs **Record QA Inspections**. Without it the dialog says so and stays read only. Enter **Accepted** and **Rejected**. Rejected pieces need a **Reason for the Rejects**, and under **Classify Rejected Pieces** each piece is set to **Rework** or **Replacement**. Rework pieces go to a new rework lot that repairs them, and replacements to a new replacement lot that makes them again. The lot's demand coverage moves to the new lots. When the inspection method requires evidence, a file under **Measurement Reports** must be uploaded before you can record.

On any other step, bad pieces are booked with **Scrap Pieces**, see [Lot Lifecycle](/handbook/production/lot-lifecycle#scrapped).

## Reversing a completion {#reverse}

On the lot page, the **Execution** tab lists the completions of each order with a **Reverse** button. It needs **Manage Production Orders** and shows disabled with a tooltip without it. **Reverse Completion** asks for a **Reason**, books the pieces back and keeps both entries on record, the original marked as reversed. An order that was **Completed** returns to **In Progress**. A completion can be reversed once. It cannot be reversed when it rejected pieces, when the next position has already used its pieces, or while the lot is on hold or finished.

## Examples

An order of 40 pieces has 25 done by the end of the shift. Open **Complete**, change **Quantity Completed** to 25 and click **Record**. Tomorrow the dialog starts with 15.

An inspection of 10 pieces finds 2 out of tolerance. Enter 8 **Accepted** and 2 **Rejected**, choose **Out of Tolerance** as the reason, and set one piece to **Rework** and one to **Replacement**. Two new lots of one piece each appear.

Someone booked 50 instead of 5 pieces. Click **Reverse** on that completion, enter the reason, and record 5 again.
