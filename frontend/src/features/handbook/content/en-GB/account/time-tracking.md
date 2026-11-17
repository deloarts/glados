---
title: Time Tracking
summary: How to connect your time tracking account to Glados, what the Time Tracking page shows about your hours, and what Glados keeps of it.
sourceRefs:
  - frontend/src/features/time-tracking/views/AccountTimeTrackingView.vue
  - frontend/src/features/time-tracking/components/AccountTimeTrackingSection.vue
  - frontend/src/features/time-tracking/components/TimeTrackingConsentDialog.vue
  - backend/src/modules/operations/application/use_cases/time_tracking/save_my_time_tracking_credentials.py
  - backend/src/modules/operations/application/use_cases/time_tracking/check_my_time_tracking_access.py
  - backend/src/modules/operations/application/use_cases/time_tracking/get_my_time_tracking_month.py
lastVerified: 2026-11-10
---

Glados can show you the hours your company's time tracking system recorded for you, next to your work. The Account tab **Time Tracking** appears only when an administrator has switched time tracking on, and only for your personal account; shared accounts and the system account cannot use it. Nobody else sees your time data, administrators included.

## Connecting your account {#connect}

The time tracking section on [My Account](/handbook/account/me#time-tracking) takes the user name and password you use in the time tracking system. Click **Save** at the top of the page. The first time, and whenever the text changes, Glados asks for your consent: it reads your time data only while you open the page, keeps none of it, and stores your password sealed so that Glados itself cannot read it. Tick that you agree and click **Confirm**. **Check Access** then shows the name you are signed in as and whether you may read **Single Days**, the **Month** and the **Year**.

When the section says your stored sign in no longer works, for example after a password change in the time tracking system, enter the password again and save. **Confirm Consent** appears when only the consent text changed. Removing the credentials also removes your consent, and the Time Tracking page stays empty until you enter them again.

## Your month {#month}

The Time Tracking page opens on the current month. The arrows move to the month before or after, **Current Month** comes back, and **Reload** fetches the data again. Future months cannot be shown. The **Overview** card shows whether you are **Clocked in** or **Clocked out**, your **First In** today, what you worked so far, today's target, your day and running balance and when you reach the target. **Accounts** lists the balances of your time accounts for the month.

The table lists every day with **Shift**, **First In**, **Last Out**, **Worked**, **Target**, **Day Balance** and **Running Balance**, and **Show bookings** lists each clock in and out. **Status** marks a day as **Normal**, **Shift-free**, **Holiday**, **Absence** or **Open**. Charts below compare worked hours with the target per day and per weekday, and the year section, opened on request, shows the whole year by month.

## Examples

**Setting it up.** You open **My Account**, type your time tracking user name and password and click **Save**. You confirm the consent, click **Check Access** and see your name with **Month** and **Year** allowed.

**Checking your balance.** On Friday afternoon you open **Time Tracking** and read in **Overview** when you reach today's target.

**After a new password.** You changed your password in the time tracking system, and the page asks you to enter your credentials again. You open **My Account**, type the new password and save.
