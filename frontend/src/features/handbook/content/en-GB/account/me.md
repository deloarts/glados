---
title: My Account
summary: How to change your name, email, photo, date format, start page and look, how to change your password, and where your time tracking sign in goes.
sourceRefs:
  - frontend/src/features/account/views/AccountMeView.vue
  - frontend/src/features/account/components/AccountPasswordDialog.vue
  - frontend/src/features/time-tracking/components/AccountTimeTrackingSection.vue
  - backend/src/modules/platform/application/use_cases/user/update_user.py
  - backend/src/modules/platform/application/use_cases/user/upload_user_avatar.py
lastVerified: 2026-11-10
---

Account, **My Account** holds what belongs to you alone: your name, your photo and how Glados looks and behaves for you. Change the fields you want and click **Save** at the top; nothing changes for anyone else. On a phone the page shows only the look, and the rest waits for a larger screen.

## Profile and photo {#profile}

**Full Name** is how colleagues see you in lists, histories and mails. **Username** is what you type to sign in, and **Email** is where Glados sends your mails. **Upload Photo** sets the picture shown next to your name, from a JPEG, PNG, WebP or GIF file, and **Remove Photo** takes it away again after a confirmation. Without a photo Glados shows your initials. When file storage is not enabled, both photo buttons show disabled and a note says why.

## Date format and start page {#regional}

**Date Format** sets how dates are shown to you, and the example under it shows today in that format. Times are always shown with 24 hours. **Start Page** is the page of the sidebar you land on after signing in.

## The look {#look}

**Preset**, **Primary Color** and **Surface** choose the colours of Glados, and **Dark Mode** switches to a dark background. **Flat Buttons**, **Table Gridlines** and **Table Line Coloring** change how buttons and tables are drawn, and the **Preview** next to them shows the result before you save.

## Changing your password {#password}

**Change Password** opens a dialog with **Current Password**, **New Password** and **Confirm Password**. Your current password is required, and the two new ones have to match. After the change every other session of yours ends and every trusted device asks for a code again, as [Sessions](/handbook/account/sessions#automatic) explains. An account from the company directory shows "Your password is managed by the directory." instead, because its password is changed there.

## Time tracking {#time-tracking}

When time tracking is switched on for this installation, your personal account also shows a time tracking section here. You enter the user name and password of your time tracking account, confirm the consent and save. [Time Tracking](/handbook/account/time-tracking) explains the section and the page that shows your hours.

## Examples

**A new surname.** You change **Full Name** and click **Save**. Your colleagues see the new name from then on.

**A darker screen in the hall.** You switch **Dark Mode** on, check the **Preview** and click **Save**.

**A forgotten old password.** You cannot change it without your **Current Password**. Ask an administrator to set a new one for you, which signs you out everywhere.
