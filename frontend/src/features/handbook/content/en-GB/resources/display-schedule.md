---
title: Display Times
summary: How the wall displays switch off at night, at the weekend and on holidays, and how to switch one off or on by hand.
sourceRefs:
  - backend/src/modules/operations/domain/value_objects/display_schedule.py
  - backend/src/modules/operations/domain/services/display_power_rules.py
  - backend/src/modules/operations/application/services/display_calendar.py
  - backend/src/modules/operations/application/use_cases/terminal/terminal_admin.py
lastVerified: 2026-11-10
---

Wall displays do not need to run when nobody is there. Each infoscreen can say when its displays are on, and every display showing that screen switches its monitor within a few seconds. You can also switch one display off or on by hand for a while.

## Setting the times of a screen {#schedule}

On Resources, [Infoscreens](/handbook/resources/infoscreens), right click a screen and choose **Display Schedule**, or use the calendar button of its row while **Show Actions** is on. The same times are in the screen's editor under **Display Times**. The **Schedule** column sums up the times of each screen. Changing the times needs **Write Infoscreens**, and without it the button shows disabled with a tooltip.

With a tick in **Always on**, the default, the displays never switch off by schedule. Take the tick away and a grid of weekdays and half hours appears, starting with 06:00 to 18:00 from Monday to Friday and the weekend off. The displays are on in the filled half hours and off in the rest, read in the time of this installation. Click a half hour to switch it, or drag across several days and hours to fill or clear the whole block, depending on the first half hour you pressed. Clicking a weekday switches the whole day, and clicking a time switches that half hour on every day. **Copy Monday to Weekdays** gives Tuesday to Friday the times of Monday, and **All On** and **All Off** fill or clear the week.

A day can be on in at most six separate stretches. A day with more is marked in red and cannot be saved until you join some.

## Holidays

**Switch off on holidays** keeps the displays off all day on every holiday listed under Resources, [Holidays](/handbook/resources/holidays). It works with or without set times, so a screen that runs day and night can still go dark on Christmas.

## Switching one display by hand {#override}

On Resources, [Terminals](/handbook/resources/terminals), right click a display and choose **Switch Display Off or On**, or use its button next to **Reload** while **Show Actions** is on. Pick **Switch Off** or **Switch On** and how long. The default lasts until the screen's times change next, so a display switched on in the evening goes back to its schedule the next morning. You can also pick a date and time within the next 31 days. **Back to Schedule** ends the switch by hand at once. The **Display** column shows a switch by hand with its end. This needs **Manage Terminals**, and without it the button shows disabled with a tooltip.

## What the display does

A display that is off cuts its picture, and a TV that listens to remote control over HDMI goes to standby too. A display that cannot reach Glados keeps its last state, and one that starts up stays on until it hears from Glados. A display waiting for approval or revoked stays on.

## Examples

**Office hours.** You open **Display Schedule** on Hall board, take the tick away from **Always on** and keep 06:00 to 18:00 on working days. The displays go dark at six in the evening and come back at six.

**Two shifts.** You drag Monday from 05:30 to 22:00 and click **Copy Monday to Weekdays**. You drag Saturday from 06:00 to 12:00, and Sunday stays off.

**A visitor in the evening.** At 19:00 you choose **Switch On** on Hall 1 entrance. It stays on until the schedule switches it on anyway the next morning at 06:00, then follows its times again.
