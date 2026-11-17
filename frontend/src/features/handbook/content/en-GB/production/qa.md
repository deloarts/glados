---
title: QA Inspections
summary: What the QA tab lists, how to filter it, and how to start an inspection, attach evidence and record its result on the QA task page.
sourceRefs:
  - frontend/src/features/production-qa/components/QaControls.vue
  - frontend/src/features/production-qa/components/QaViews.vue
  - frontend/src/features/production-qa/components/QaTaskTable.vue
  - frontend/src/features/production-qa/views/ProductionQaTaskView.vue
  - frontend/src/features/production-qa/components/QaTaskControls.vue
  - backend/src/modules/fulfillment/application/use_cases/production_order/get_qa_tasks.py
lastVerified: 2026-11-10
---

An inspection is a position of a lot like any other, and its production order is the QA task. The order is queued as soon as the lot is created. With **Require QA Inspection** on under System Settings, Production, every new lot whose route does not end with an inspection gets one added. The **QA** tab under Production lists these tasks for the people who inspect, and a click on a row opens the task's own page.

## The worklist {#list}

The bar at the top counts the tasks that are **Ready** and those still missing evidence. **Read only** shows when you lack **Record QA Inspections**, which every result needs. **Readiness** says where a task stands: **Waiting** while the step before it has not made pieces available, **Ready** when it can start, then **In Progress**, **Paused**, **Done** or **Canceled**. **Evidence** shows whether the measurement report a method asks for is on file.

By default the list shows open tasks that can be worked now. **Show Completed**, **Show Canceled** and **Show Future Tasks** add the finished ones, the canceled ones, and the ones that cannot start yet, are not planned or are planned after today. The search finds an order number, and the quantity filter takes a minimum and a maximum.

## The task page {#task}

The left side shows the part with its material, lot, position, project, quantity and planned start, and the 3D model and the drawing when they are on file. The right side shows the inspection method, its instructions and notes, the results recorded so far and the evidence files.

**Start QA**, or **Resume QA** for a paused task, starts the inspection. It needs **Write Production Orders** and **Record QA Inspections**, and waits until the step before it has finished pieces. **Record Result** opens the completion dialog with **Accepted** and **Rejected**, explained in [Recording Completions](/handbook/production/completions#rejects). **Add Document** takes photos or files straight into the evidence, and **Inspection Report** prints the lot's report. Without the permissions these buttons show disabled, with a tooltip that names the permission they need.

## Evidence {#evidence}

When the inspection method requires evidence, the result can only be recorded after a measurement report is uploaded. The task shows this as a warning, and the worklist counts it under missing evidence. Upload the report in the evidence panel, or photograph it with **Add Document** on a tablet or phone.

## Examples

A lot of 12 shafts has finished turning. Its QA task shows **Ready**. Open it, click **Start QA**, measure the shafts and record 12 **Accepted** with **Record Result**.

A task shows missing evidence. Open it, upload the measurement report in the evidence panel, and **Record Result** can save the result.

You want to see last week's inspections. Turn on **Show Completed** and sort by planned date.
