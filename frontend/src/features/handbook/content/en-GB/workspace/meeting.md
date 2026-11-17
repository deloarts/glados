---
title: Meeting Page
summary: What the page of one meeting shows, how attendees, documents and the history work, and what marking it invalid and a follow-up meeting do.
sourceRefs:
  - frontend/src/features/meetings/views/MeetingDetailView.vue
  - frontend/src/features/meetings/components/MeetingControls.vue
  - frontend/src/features/meetings/components/MeetingFormDialog.vue
  - frontend/src/features/meetings/components/MeetingInfoCard.vue
  - frontend/src/features/meetings/components/MeetingDocumentsCard.vue
  - frontend/src/features/meetings/components/MeetingOpenPointsCard.vue
  - backend/src/modules/workspace/application/use_cases/meeting/meetings.py
  - backend/src/modules/workspace/domain/services/meeting_rules.py
  - backend/src/modules/workspace/domain/services/meeting_tags.py
lastVerified: 2026-11-11
---

The page of a meeting holds its notes. The bar at the top shows the number, whether the meeting is valid, its name, date, time and location, the project or product it belongs to, **Sent** and **Printed** once the notes went out, and the meeting's tags. On the left are the cards with the notes, explained in [Meeting Cards](/handbook/workspace/meeting-cards). On the right are the **Meeting** card with the attendees, the **Documents** and the **Distribution**, which [Printing and Sending Meeting Notes](/handbook/workspace/meeting-distribution) explains. **Back to Meeting Notes** returns to the tab.

## Attendees and their status

**Edit Meeting** opens the form with **Name**, **Date**, **Start**, **End**, **Location** and **Tags**, which are explained under [Meeting Notes](/handbook/workspace/meeting-notes). Under **Attendees** you type a name and pick a Glados user, a contact or, for anyone else, **Add "…" as Guest** with an optional e-mail address. A guest can be kept with **Save "…" as a New Contact**. Each attendee is **Present**, **Excused** or **Distribution**, which means the person receives the notes without attending. Offering contacts needs the permission **Read Contacts**.

A guest who asks to be forgotten is removed with **Anonymise Guest** on the **Meeting** card, which needs **Manage Meetings**.

## Next meeting and follow-up

Under **Next Meeting** you note the agreed date, time and place, which is optional and shows on the **Meeting** card and in the PDF. **Create Follow-up Meeting** creates a meeting of the same project or product with the name, location, tags and attendees copied. It takes the next meeting's date, time and place. Without a time it keeps this meeting's start time, and without a date it is one week later.

The follow-up shows an **Open Points** card with the open todos of the meeting it follows and of the meetings before that one. Each links to its card, and ticking one off there ticks off the original.

## Documents

**Add File** or a drop on the **Documents** card uploads images up to 10 MB and PDFs up to 50 MB. An image pasted into a card lands here too, marked **Image in a card**. The pencil beside a file renames it, and the name keeps its extension. Deleting a file removes it from the meeting and from storage, and removing an image from a card's text leaves the file here.

## History

**History** lists everything that happened: the meeting created and edited, cards added, changed and deleted, todos added, ticked off and opened again, files added and deleted, every print, download and send, and marking invalid and restoring. A print or a send links its snapshot. Each card also keeps its own versions, see [Meeting Cards](/handbook/workspace/meeting-cards#history).

## Invalid and restored

**Mark Invalid** asks for a **Reason**. The notes turn read only, the page says who marked it and why, and its open todos leave everyone's todo page. **Restore** makes the meeting valid and editable again, with an optional note. Both need the permission **Manage Meetings**. Editing, adding cards and files and **Create Follow-up Meeting** need **Write Meetings**. A button you lack the permission for stays visible but disabled, and its tooltip names the permission.

## Examples

**A customer contact who only reads the minutes.** You add the customer's purchaser as **Distribution**. The PDF lists the purchaser under Distribution, and the send suggests the address.

**The next review.** You note the next meeting for Thursday at 10:00 in Hall 2. Later **Create Follow-up Meeting** creates it for Thursday at 10:00 in Hall 2 with the same attendees, and its **Open Points** card lists the todos still open.

**The wrong project.** A meeting was recorded on 26-0142 instead of 26-0143. You mark it invalid with the reason "Recorded against the wrong project", and its todos disappear from the todo pages.
