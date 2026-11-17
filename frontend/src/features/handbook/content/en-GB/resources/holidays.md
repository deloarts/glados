---
title: Holidays
summary: How public holidays and plant shutdowns close the machines, how a machine can still work on such a day, and what else uses the list.
sourceRefs:
  - backend/src/modules/platform/application/use_cases/tenant_holiday/tenant_holidays.py
  - backend/src/modules/platform/domain/services/tenant_holiday_rules.py
lastVerified: 2026-11-10
---

The **Holidays** list holds the days the whole plant does not work, such as public holidays and the summer or Christmas shutdown. The schedule plans no work on them, so delivery dates move past them on their own.

## Adding a holiday

**Add Holiday** opens the form. **Name** is required and can be up to 200 characters long. **Category** is either Public Holiday or Plant Shutdown. **From** is required. **To** is optional and shows Same day when empty, so a single day needs only **From**. Both dates count, **To** cannot be before **From**, and one holiday can span at most 366 days.

A holiday does not repeat. Each entry is one date range, so add next year's public holidays as new entries. **Reload** fetches the list again, for example after a colleague changed it.

## What a holiday closes

Both categories have the same effect. They close every machine and the default calendar, which manual work is planned on. The category only tells people why the plant is closed. Any change to the list replans the schedule at once.

A machine can still work on a holiday. Add a calendar exception for that date under **Manage Calendar** on the machine, and the exception wins over the holiday for that one machine.

An infoscreen can switch the displays showing it off on holidays and can show the next holiday, both taken from this list.

## Managing the list

The table shows **#**, **Name**, **Category**, **From**, **To** and **Days**, the number of calendar days the entry covers. You need the permission **Write Production Machines** to add, edit and delete holidays. Without it the buttons show disabled with a tooltip. Holidays are deleted after a confirmation, not archived, so a deleted holiday is gone and its days follow the normal working hours again.

## Examples

**A public holiday.** Add Labour Day as a Public Holiday with **From** 1 May and **To** left empty. **Days** shows 1, and no work is planned on that day.

**Christmas shutdown.** Add Christmas shutdown as a Plant Shutdown from 24 December to 6 January. **Days** shows 14, and the schedule moves work out of that range to the working days after it.

**Maintenance during the shutdown.** The maintenance crew needs the milling machine on 28 December. Add a calendar exception for that date on the milling machine with a start time and the minutes it works. Only that machine is open that day.
