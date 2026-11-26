---
title: Inspection Methods
summary: What an inspection method is, how its default times, QA machine and evidence rule reach the QA steps, and how the list order works.
sourceRefs:
  - backend/src/modules/catalogue/application/use_cases/inspection_method/update_inspection_method.py
  - backend/src/modules/catalogue/application/use_cases/inspection_method/archive_inspection_method.py
  - backend/src/modules/catalogue/domain/policies/inspection_method_rules.py
  - backend/src/modules/catalogue/domain/services/label_name_rules.py
  - backend/src/modules/catalogue/application/services/catalogue_list_order.py
  - backend/src/modules/fulfillment/domain/policies/wait_after.py
lastVerified: 2026-11-26
---

An inspection method is a kind of quality check, such as a visual check, a thread gauge check or a measurement on the coordinate measuring machine. Every inspection step of a lot uses one. The method carries the defaults a new inspection step starts with and decides whether a completion needs a measurement report. The list lives under Resources, **Inspection Methods**.

## Name, description and colours

Each method has a **Name** and a **Description** in every language of the interface. The name is required in the default language and can be up to 200 characters long. No two methods that are not archived may show the same name in the same language, ignoring upper and lower case. **Label Color** and **Font Color** set how the method appears as a label, and **Preview** shows the result.

## Default times

**Default setup [min]** and **Default per piece [min]** are optional. Setup takes a whole number of minutes, per piece takes minutes with up to two decimals, and both take 0 or more. They are copied onto new inspection steps only, where you can still change them per step; editing the method later leaves existing steps alone. When a field is empty, the step has no time estimate for that part.

## Default QA machine

**Default QA machine** is optional and shows No machine (manual QA) when empty. It offers only machines marked as a QA or measuring machine. When a lot is created, the machine is filled in on the production order of its inspection step. Without one, the inspection stays manual work, because Auto-Plan never picks a machine for inspection work on its own.

## Requires evidence

Tick **Requires evidence** when a check must be documented. A completion for a step with this method can only be recorded once at least one measurement report file is attached to the production order.

## Waiting after the check {#wait-after}

**Wait after the check [min]** is optional and empty for new methods. Enter the minutes the pieces have to wait after a check of this method before the next step may start, such as for a lab result. The wait runs on the clock, overnight and over weekends too, and the next step is planned for when it is over, also once the check itself is reported complete. When the check is the last step of a lot, the lot counts as late until the wait is over, and saving a change replans the schedule.

## Managing the list

You need the permission **Write Inspection Methods** to create, edit, move, archive and restore methods. Without it the buttons show disabled. Methods are archived, not deleted, so existing steps keep theirs. A method cannot be archived while it is the **Default Inspection Method** of the production settings; choose another default there first. **Show Archived** lists archived methods again, and restoring is refused while a live method already uses the same name. A click on a row opens its details.

The order of the list is the order the pickers offer. If you may edit inspection methods, drag a row by the grip in its first column to its new place. The grip shows only while no sort, search or filter is active. New methods go to the end.

## Examples

**A visual check.** Create Visual check with 0 in **Default setup [min]** and 0.5 in **Default per piece [min]**. A new inspection step for 40 pieces starts with an estimate of 20 minutes, and the inspector can adjust it on the step.

**Measuring with evidence.** Create CMM measurement, choose your measuring machine as **Default QA machine** and tick **Requires evidence**. New lots put their inspection on that machine, and the step cannot be completed until the report is attached.

**Waiting for a lab result.** Create Salt spray test with 2880 in **Wait after the check [min]**, two days. A final check that ends on Monday at 10:00 has its result on Wednesday at 10:00, so a lot due on Wednesday is on time. Ending on Tuesday afternoon, the same lot counts as late.

**Retiring the default.** You try to archive Final inspection, which is the **Default Inspection Method**. Glados refuses. Set another default in the production settings, then archive it.
