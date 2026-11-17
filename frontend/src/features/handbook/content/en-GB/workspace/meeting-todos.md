---
title: Meeting Todos
summary: How the todos written in a meeting reach the todo page of their owners, where they show and how they are ticked off.
sourceRefs:
  - frontend/src/features/todo/views/TodoView.vue
  - frontend/src/features/todo/utils/buildTodoTasks.ts
  - frontend/src/features/todo/composables/useTodoTasks.ts
  - backend/src/modules/fulfillment/application/use_cases/todo/get_todo_sources.py
  - backend/src/modules/workspace/domain/services/meeting_rules.py
lastVerified: 2026-11-10
---

A todo written on a card of a meeting lands on the todo page of every Glados user who owns it, under the category **Meetings**. Everything else on the todo page Glados works out itself each time the page opens, from open orders, demands and lots: an order still to submit, a delivery to chase, a lot to plan. A meeting todo is different, because someone wrote it down and gave it to you. How todos are written is explained in [Meeting Cards](/handbook/workspace/meeting-cards).

## Which todos show

A meeting todo shows on your todo page while it is open, you are one of its owners and the meeting is valid. It needs no permission, since it is yours. When a meeting is marked invalid, its open todos leave the todo pages until a manager restores it. A todo owned only by contacts, such as the customer confirming a colour, reaches no todo page at all. The task names the todo, the meeting number and name, and the scope of its card.

## The four columns

Every task on the todo page sits in one column by its date. **Overdue** holds what is past its date, **Today** what is due today and **This Week** what is due in the next seven days. **Blockers** holds what has no date but stops work, and a meeting todo without a date waits there too. A task due later than next week does not show yet.

By default the page shows only what is urgent: what is overdue, due today, of high priority, or what stops work. A meeting todo is yours, so it always shows on the default view, whatever its date. **Show all** with the number of hidden tasks shows the others.

## Categories

The views bar has one toggle per category: **Procurement** for orders and demands, **Shop Floor** for production orders, **Planning** for lots and schedule conflicts, and **Meetings** for the todos of meetings. Each shows how many tasks it holds, and **All Categories** turns every category on again. You see a task of the first three categories only when you hold the permission to act on it, such as **Write Orders** for submitting an order.

## Ticking a todo off

Clicking the task opens the meeting at the todo's card, where you tick it off. Ticking it off marks it done for everyone, and it leaves the todo page of every owner at once. An owner ticks off their own todo, and anyone with **Write Meetings** ticks off any. On a follow-up meeting the same todo also shows under **Open Points**, and ticking it there ticks off the original.

## Examples

**A todo from yesterday's review.** Jonas made you owner of "Send the sensor datasheet", due tomorrow. It shows under **This Week** in **Meetings** right away, and the day after tomorrow under **Overdue**.

**Only the meeting todos.** You switch off **Procurement**, **Shop Floor** and **Planning** and keep **Meetings**. The page shows only what your meetings gave you.

**Done in the meeting.** A colleague ticks your todo off during the follow-up meeting. It leaves your todo page at once.
