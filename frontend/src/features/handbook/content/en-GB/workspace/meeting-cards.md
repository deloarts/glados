---
title: Meeting Cards
summary: How the notes of a meeting are written as cards with a scope, text, mentions, decisions and todos, and how several people write at once.
sourceRefs:
  - frontend/src/features/meetings/components/MeetingCard.vue
  - frontend/src/features/meetings/components/MeetingCardEditor.vue
  - frontend/src/features/meetings/components/MeetingScopePopover.vue
  - frontend/src/features/meetings/components/MeetingCardTodos.vue
  - frontend/src/features/meetings/components/MeetingCardDecisions.vue
  - frontend/src/features/meetings/components/MeetingMergeDialog.vue
  - frontend/src/features/meetings/components/MeetingCardHistoryDialog.vue
  - backend/src/modules/workspace/application/use_cases/meeting/cards.py
  - backend/src/modules/workspace/application/use_cases/meeting/todos.py
  - backend/src/modules/workspace/domain/services/meeting_markdown.py
lastVerified: 2026-11-10
---

The notes of a meeting are cards, one per topic. **Add Card** adds one, and a click on a card opens it for editing. Each card saves on its own with **Save Card**, so several people can write different cards of the same meeting at once.

## Scope and icon

The scope says what a card is about, such as Vacuum gripper or Delivery date. Click **Add a Scope** at the top of the card and type it. The field suggests the scopes already used on this project or product, the most used first, and offers **Use It** when yours differs from an existing one only in spelling. **Icon, Optional** adds one of twelve icons, such as Mechanics, Software or Risk. The scope is plain text and links to nothing else in Glados.

## Writing the text

The editor has two modes over the same text. **Visual** shows the formatting as you type, and the toolbar sets bold, italic, headings, lists, inline code and links. **Markdown** shows the text with its marks, and only headings, bold, italic, lists two levels deep, links, inline code, mentions and images are kept, so any other syntax becomes plain text. Type **@** to mention a Glados user. A mentioned colleague is notified once per card, see [Notifications and Permissions](/handbook/account/notifications#kinds).

**Internal, left out of print and mail** marks a card for your own team only. It carries a lock and is left out of every PDF unless the print or send includes internal cards.

## Decisions and todos

**Add Decision** records what the meeting decided. The PDF prints the decisions with their card and repeats them in a summary.

**Add Todo** records a task with **Owners**, an optional **Due** date and an optional **Note**. Owners are Glados users or contacts of the meeting. A user who owns an open todo finds it on their todo page under Meetings, see [Meeting Todos](/handbook/workspace/meeting-todos). A todo owned only by contacts, such as the customer confirming a colour, is tagged **Not on a Todo Page** and notifies nobody. Ticking a todo off marks it done for everyone. Anyone with **Write Meetings** ticks off any todo, and an owner ticks off their own.

## Writing at the same time

While you edit a card, the others see "Jonas is editing" on it. When someone saved the card while you were writing, your save opens **Merge Changes** with their text, your text and the changes between them. You merge both into **Merged Text** and save that.

Glados keeps your unsaved text in the browser. After a reload or a lost connection the card offers **Restore Draft**, or **Merge Draft** when someone saved the card since, and **Discard** throws the draft away.

## Card history {#history}

**Card History** lists the versions of a card with the changes from one to the next. Saves by the same person within 10 minutes count as one version. **Restore This Version** makes an old text the current one again, as a new version.

Writing needs the permission **Write Meetings**. Without it the buttons stay visible but disabled.

## Examples

**Two people in one meeting.** Anna writes the card Mechanics while Jonas writes Software. Both save without waiting for each other.

**A todo for the customer.** On the card Paint you add the todo "Confirm the colour" owned by the customer's contact. It shows in the PDF and on the follow-up's open points, but on no todo page.

**A clash.** You and Anna both changed the card Schedule. Your save opens **Merge Changes**, you keep her new date and your note, and save the merged text.
