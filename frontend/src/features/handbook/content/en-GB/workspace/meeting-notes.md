---
title: Meeting Notes
summary: How the Meeting Notes tab of a project or a product lists its meetings, how you start a new one, and how scopes are renamed.
sourceRefs:
  - frontend/src/features/meetings/components/MeetingNotesTable.vue
  - frontend/src/features/meetings/components/MeetingNotesViews.vue
  - frontend/src/features/meetings/components/MeetingNotesControls.vue
  - frontend/src/features/meetings/components/MeetingScopeRenameDialog.vue
  - backend/src/modules/workspace/application/use_cases/meeting/meetings.py
  - frontend/src/features/meetings/components/MeetingTagInput.vue
  - backend/src/modules/workspace/application/use_cases/meeting/scopes.py
  - backend/src/modules/workspace/application/use_cases/meeting/tags.py
lastVerified: 2026-11-11
---

The **Meeting Notes** tab of a project or a product lists the meetings held about it, such as a design review or a site visit with the customer. Every meeting belongs to exactly one project or one product and has a number such as MTG-26-0021, in the format an administrator sets under **Settings**, **Numbering**. Everyone signed in to Glados can read every meeting. Click a row to open the meeting's page, where the notes are written, printed and sent, see [Meeting Page](/handbook/workspace/meeting).

## What the table shows

Each row shows the status, the date and time, the scopes of the meeting's cards, the name with the number below it, the meeting's tags, the start of the notes, the open todos, the attendees and the location. **Status** says **Valid** or **Invalid**, and small icons show whether the notes were sent or printed. **Scope** shows the topic of every card as a chip, and a chip of an internal card is marked as such. **Open Todos** counts the todos nobody has ticked off yet and names the overdue ones in red. The field above **Tags** picks one of the tags in use, and the table then lists only the meetings that carry it, whatever its case. **Clear** on the views bar removes the filter again.

## Starting a meeting

**New Meeting** opens the form. **Name**, **Date**, **Start** and **End** are required, and the end may not lie before the start. **Location** is optional free text, such as a room or a Teams call. **Tags** are optional too, such as Milestone or Acceptance, so the meeting is easy to find again. While you type, the field offers the tags other meetings carry, and Enter or a comma adds what you typed as a new one. A meeting carries up to 10 tags of at most 40 characters each, and a tag that repeats another in a different case is kept once. Under **Attendees** you add Glados users, contacts and guests, each with their status. Under **Next Meeting** you can note when and where the next one takes place, which is optional. **Create Meeting** saves it and opens its page, ready for the first card.

Creating a meeting needs the permission **Write Meetings**. Without it the button stays visible but disabled, and its tooltip names the permission.

## Views on a product

On a product the tab lists the product's own meetings and those of every project of the product too, until you press **Hide Projects**, with a **Project** column. **Group By Project** groups the rows by project. Both are on the views bar together with **Sync**, **Sort by**, **Show Invalid** and **Clear**, which brings every view back to its default. Invalid meetings are left out until you switch **Show Invalid** on.

Every column has a filter in the row under its heading: the status, such as **Not Sent**, a day or a range of days, the projects, a search in the scopes, the name and number, the notes and the location, whether the meeting has open or overdue todos, the attendees and the tag. The filters narrow the list at once, and **Clear** removes them all.

## Renaming a scope

The scope of a card is free text, so the same topic can end up spelled two ways. **Rename Scope** picks a scope used here, shows on how many cards, and renames it on every card of the valid meetings of this project, on a product also on those of its projects. It needs **Write Meetings**.

## Deleting a meeting

Right click a row, or turn on **Show Actions**, for **Open**, **Open in New Tab** and **Delete Meeting**. Deleting removes the meeting with its notes, todos and documents from every list. It needs the permission **Manage Meetings** and shows disabled without it. A meeting recorded against the wrong project is better marked invalid on its page, which keeps it on record.

## Examples

**A design review.** On project 26-0142 you press **New Meeting**, enter Design Review Gripper, today from 10:00 to 11:30, Room Danube, and add two colleagues and the customer's project manager. The meeting opens as MTG-26-0021, ready for its cards.

**All meetings of a machine.** On the product you leave **Hide Projects** off and turn on **Group By Project**. The product's own meetings and those of each of its projects show in groups.

**Finding the milestones.** You tag the meetings that close a project phase with Milestone. Later you pick Milestone in the field above **Tags**, and the table shows only those meetings.

**One topic, two spellings.** Some cards say Vacuum Gripper and others Vacuum gripper. **Rename Scope** renames the first to the second, and every card shows the same chip.
