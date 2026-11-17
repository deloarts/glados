---
title: Notifications and Permissions
summary: What the notifications of your account tell you, how to mark them read, and how to see which permissions you hold.
sourceRefs:
  - frontend/src/features/account/views/AccountNotificationsView.vue
  - frontend/src/features/notifications/components/NotificationPanel.vue
  - backend/src/modules/platform/application/use_cases/notification/handle_event_notifications.py
  - frontend/src/features/account/views/AccountPermissionsView.vue
  - frontend/src/shared/utils/permissionGroups.ts
lastVerified: 2026-11-10
---

Glados tells you when something happens that concerns you, such as an order of yours being canceled or a project assigned to you. These notifications show in the bell at the top of every page and on the Account tab **Notifications**. The Account tab **Permissions** next to it shows what you may do in Glados.

## Your notifications {#notifications}

The number on the bell counts the notifications you have not read yet. Glados looks for new ones every minute, so a notification can take a moment to appear. Click the bell for the latest ones, or open Account, **Notifications** for the whole list. Each entry shows a title, a short message and when it happened, and an unread one carries a dot. Click an entry to mark it read, or click **Mark all read** to clear the dot from all of them at once.

**Filter by date** narrows the list to a range of days, and **Clear** shows everything again. **Sync** loads new notifications without waiting for the next minute.

## What you are told about {#kinds}

Notifications come from the work you are part of. You hear when an order or a demand of yours is canceled, when delivered pieces are rejected, when an item you are waiting for is delivered, and when a lot ends short or pieces are scrapped. You also hear when a project or product is assigned to you, and when someone takes over a document you were editing, ends your editing or marks a revision invalid. When someone mentions you or makes you the owner of a todo in a meeting, Glados waits five minutes and then sums up in one notification everything in that meeting that concerns you, such as "Jonas mentioned you twice and assigned you 2 todos in MTG-26-0021". Clicking it opens the meeting. Changes to your own account show too, such as **Permissions updated** or a sign out by an administrator. Depending on how mail is set up, some of these also reach you as a mail.

## Your permissions {#permissions}

Account, **Permissions** lists every permission of Glados in groups such as Orders, Production Lots or Printing. A permission you hold shows a green tick, and one you do not hold is greyed out with a lock. Each row names the permission as it is labelled everywhere else, such as **Write Orders**, and says in one sentence what it allows. The list includes what you get through a user group, so it is the full picture of what you may do. The system account holds every permission, and the tab says so at the top.

Only an administrator can change your permissions. When that happens, you get the notification **Permissions updated**, and buttons you could not use before become active. A button you lack the permission for stays visible, but shows disabled, and its tooltip usually names the permission.

## Examples

**An order canceled.** The bell shows 1. You click it, read that your order was canceled, and the dot disappears.

**Looking back at last week.** On **Notifications** you pick last Monday to Friday under **Filter by date** and see only the notifications of those days.

**A disabled button.** **Create Token** is greyed out for you. On **Permissions** you see a lock at the token permission, so you ask an administrator for it.
