---
title: Production Machines
summary: How to set up a production machine, its working hours, calendar exceptions and downtimes, and how each of them affects planning.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_machine/create_machine.py
  - backend/src/modules/fulfillment/application/use_cases/production_machine/archive_machine.py
  - backend/src/modules/fulfillment/application/use_cases/production_machine/working_hours.py
  - backend/src/modules/fulfillment/application/use_cases/production_machine/calendar_exceptions.py
  - backend/src/modules/fulfillment/application/use_cases/production_machine/downtimes.py
  - backend/src/modules/fulfillment/application/use_cases/production_machine/move_machine.py
  - backend/src/modules/fulfillment/domain/services/production_machine_rules.py
  - backend/src/modules/fulfillment/domain/services/production_machine_status_rules.py
  - backend/src/modules/fulfillment/domain/services/machine_downtime_rules.py
lastVerified: 2026-11-10
---

The **Production Machines** list holds every machine the schedule can plan work on. A machine says which fabrication methods it can do, when it works and when it is down, and the schedule only places an order on a machine that can do all of its steps and has working time.

## Setting up a machine

**Internal Name**, **Vendor** and **Model** are required. **Capabilities** lists the fabrication methods the machine can do. **Max Part Dimension** is optional free text, such as 3000 x 1500 mm, and **Note** takes anything else. Tick **QA / measuring machine** for a measuring machine: it takes inspection work only, never fabrication, so its capabilities are cleared and the field is locked.

## Status

The **Status** column is set by Glados. A machine is Down while a downtime is open. Otherwise it is Running when one of its orders is in progress, Paused when one is paused, and Idle when neither.

## Working hours and exceptions {#working-hours}

**Default Calendar** in the toolbar sets the weekly hours every machine uses unless it has its own, and manual work is planned on it too. Saving it needs the permission **Write Production Machines**.

**Manage Calendar** on a row opens the calendar of one machine. Under **Working Hours**, **Use Global Default** follows the default calendar, while **Custom Override** gives the machine its own weekly shifts. **Calendar Exceptions** change a single date, at most one per date: tick **Closed** for a day off, or set a **Start** and the available minutes, 0 to 1440, for a maintenance window or an extra shift. An exception also opens a machine on a holiday.

## Downtimes {#downtimes}

A downtime records that a machine cannot work. **Started At** is required, an empty **Ended At** means it is still ongoing, and **Reason** is one of Breakdown, Maintenance, Tooling Change, No Operator, No Material or Other, with an optional **Note**. A machine can have only one ongoing downtime, and finished downtimes of one machine may not overlap. The schedule leaves out the time a machine is down, and Auto-Plan skips it. **Downtimes** in the toolbar lists them for all machines.

## Managing the list

You need the permission **Write Production Machines** to create and edit machines, their calendars and downtimes, to move them and to archive or restore one. Without it the buttons show disabled. A machine cannot be archived while it still has queued, in progress or paused production orders. Editing, archiving and restoring replan the schedule. **View Machine** opens the machine page.

The order of the list is also the order of the schedule board and of every machine list. If you may edit machines, the first column shows a grip in every row. Hold the grip and drag the row to its new place; a line shows where it will land. The grip shows only while no sort, search, filter or **Group by** is active, since those show the rows in another order. New machines go to the end.

## Examples

**A new laser.** Create the laser with its vendor and model and choose Laser cutting under **Capabilities**. It works the default hours, and Auto-Plan can now place laser steps on it.

**An extra Saturday.** Under **Calendar Exceptions** of the lathe, add next Saturday with **Start** 06:00 and 480 minutes. The lathe works from 06:00 to 14:00 that day, although its weekly hours leave Saturday free.

**A breakdown.** Add a downtime with **Reason** Breakdown and leave **Ended At** empty. The machine shows Down and Auto-Plan plans around it. When it runs again, end the downtime.
