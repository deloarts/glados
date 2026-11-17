---
title: Printing and Sending Meeting Notes
summary: How meeting notes become a PDF, how they are sent to the customer, what the issue on the PDF means, and how to see what went out and what changed since.
sourceRefs:
  - frontend/src/features/meetings/components/MeetingPrintDialog.vue
  - frontend/src/features/meetings/components/MeetingSendDialog.vue
  - frontend/src/features/meetings/components/MeetingSnapshotDialog.vue
  - frontend/src/features/meetings/components/MeetingSentChangesNotice.vue
  - backend/src/modules/workspace/application/use_cases/meeting/distribution.py
  - backend/src/modules/workspace/domain/services/meeting_issue.py
  - backend/src/modules/platform/domain/services/mail_attachment_policy.py
lastVerified: 2026-11-10
---

The notes of a meeting go out as a PDF: printed, downloaded or sent by mail. **Print** and **Send** on the meeting page open their dialogs. Every print, download and send is listed on the **Distribution** card, and Glados keeps a snapshot of exactly what each PDF contained.

## What the PDF contains

The PDF shows the meeting's facts, the attendees grouped as present, excused and distribution, the cards with their scope and author, the decisions with a summary, the todos and the list of documents. **Include Todos** and **List Documents** are on by default. Internal cards are left out unless you tick **Include Internal Cards** for this one PDF, so the same notes can go to the customer. You pick the PDF's **Language** in the dialog.

## Issue and draft

The PDF carries an issue. Every send is the next issue, such as Issue 2 · 6 Nov 2026. A print or a download carries the last issue while nothing changed since it was sent, otherwise it says Draft after issue 2, and before the first send just Draft.

## Printing and downloading

**Download PDF** saves the file. Printing to a document printer needs the permission **Print Documents**. When someone changed a card while the dialog was open, Glados refuses the PDF and names the card, the page shows the notes as they are now, and pressing the button again builds the PDF from them.

## Sending

**Send** fills **To** with suggestions: the attendees who are contacts or guests with an address, and the project's and the product's contacts that receive meeting notes. The customer's other contacts and the customer's own address are offered but not ticked. **CC** starts with you. **Subject** and **Text** come from the admin template Meeting Notes in the chosen language, and the text ends with the clause that the minutes count as accepted unless someone objects within 7 days. You can change both before sending.

The PDF is always attached. **Attach Documents of the Meeting** adds the meeting's files while the mail stays under the attachment limit the administrator set, 10 MB unless changed, and the dialog names the files left out. When the mail server refuses the mail, the dialog shows its error and nothing is recorded. Sending needs **Write Meetings** and **Send Mail**, and an invalid meeting cannot be sent.

## What went out and what changed since {#distribution}

On the **Distribution** card, **View as Sent**, **View as Printed** or **View as Downloaded** shows the notes as that PDF contained them, with the recipients and the attached files. **Changes Since** compares that snapshot with the notes today: cards added, removed and changed with their lines, decisions and new todos. Internal cards a snapshot left out are left out of the comparison too.

A card changed after the last send is tagged **Changed After Sending**, and a new one **Added After Sending**. A notice above the cards offers **Show Changes** and **Send Again**. Ticking a todo off counts as no change.

## Examples

**Minutes to the customer.** You press **Send** after the review. To holds the customer's project manager and the purchaser on the distribution. The internal card about pricing stays out, and the PDF says Issue 1.

**A correction.** The next day a colleague fixes a date on one card. The card shows **Changed After Sending**, **Show Changes** shows the line that changed, and **Send Again** sends Issue 2.

**Too many drawings.** The meeting has 14 MB of PDFs. The send attaches the notes and the files that fit under 10 MB and names the rest, which you share another way.
