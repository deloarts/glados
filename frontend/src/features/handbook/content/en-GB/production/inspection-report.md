---
title: Inspection Report
summary: What the inspection report of a production lot shows, where you open it and when it is complete.
sourceRefs:
  - frontend/src/features/production/lots/utils/inspectionReport.ts
  - frontend/src/shared/reports/components/ReportExportDialog.vue
  - backend/src/modules/fulfillment/domain/value_objects/lot_event_type.py
lastVerified: 2026-11-10
---

The inspection report of a production lot collects in one PDF what quality needs to show for that lot: the part, its material, every inspection with its results, and what happened to rejected pieces. You hand it to a customer with the delivery or keep it in the lot file. It is made in the same export dialog as other reports, see [Exporting and Printing Reports](/handbook/resources/report-export).

## Opening the report

Open **Inspection Report** from the print menu of a lot, from the **Print** submenu of its row in the lots table, or on its QA task. The report downloads without the permission **Print Documents** too. Sending it to a printer needs that permission, and without it **Print** shows disabled with a tooltip.

## What it shows

The report starts with a summary of the lot, with its project, quantity, due date and how many pieces were completed and scrapped. It then shows the part with its picture, revision and the names of its drawings, and the material with its source, purchase order and approval. Every inspection follows with its method, instruction, results and inspector. Rejected pieces show their reason and disposition, and attached evidence is listed with a fingerprint of each file, so a copy can be checked against it. External processing is listed with its goods receipt, and every nonconformity with its follow-up lots for rework or replacement.

When you record rejected pieces of an inspection, choose the **Reason for the Rejects**; the report shows it next to the result.

## The quality history

The last part lists the events that matter for quality, in the order they happened, with who did them. These are the creation of the lot, the approval or rejection of its material source, a switch of the material source, a hold and its release, inspections, scrapped pieces and pieces lost at receipt, follow-up lots, and how the lot ended. A lot ended early with **Complete Lot** also shows **Work in progress dropped** for good pieces that never reached the next position. A lot ended that way or with **Cancel Lot** shows **Raw material left over** for raw material that arrived but was not used. Planning changes stay out of the report and remain in the lot's own history.

## A lot that is not finished

The report shows only what Glados holds at the moment you export it. A lot that is not completed yet carries a warning at the top that the report shows its state at the time of export, not a finished inspection. Export it again once the lot is done.

## Examples

**For the customer.** A lot of 40 brackets is completed. You open **Inspection Report** from its print menu, choose English and click **Download PDF**, then attach the file to the delivery note mail.

**A lot with rework.** Three pieces failed the dimension check with the reason Hole offset. The report shows the reason next to the result and lists the rework lot under the nonconformities.

**An early copy.** QA wants the report while the lot is still in progress. The PDF carries the warning that it shows the state at the time of export.
