---
title: Messages to Terminals
summary: How to show a short message on many wall displays at once, who sees it and how long it stays.
sourceRefs:
  - backend/src/modules/operations/domain/services/terminal_broadcast_rules.py
  - backend/src/modules/operations/domain/value_objects/terminal_broadcast.py
  - backend/src/modules/operations/application/use_cases/terminal/terminal_broadcasts.py
lastVerified: 2026-11-10
---

A message to terminals puts a short text on many wall displays at once, such as a fire drill or a visit, without changing any infoscreen. You send it from Resources, **Terminals**, with **Message to Terminals**, and the number on the button shows how many messages run right now. Anyone can see the running messages. Sending and ending one needs **Manage Terminals**, and without it the buttons show disabled with a tooltip.

## Writing the message

Type the **Text**, up to 2000 characters. It can use Markdown: two stars around a word make it bold, one star makes it italic, a hash at the start of a line makes a heading and a dash starts a list. A link shows only its text and pictures are left out, since nobody can click a wall display. Pick the **Severity**, Information, Warning or Alert, which sets the colour. The **Style** is **Banner**, a strip above the screen while the pages keep running, or **Full Screen**, which covers the whole screen.

## How long it stays

**Show Until** is required and lies at most 30 days ahead. **15 Min**, **1 Hour** and **End of Day** fill it in, and the date picker takes any other time. Each display hides the message by itself at that time. **End Now** in the list of running messages ends one earlier.

## Who sees it

The **Audience** is **All Terminals** unless you pick. **Pick Terminals** reaches the displays you choose, **Pick Infoscreens** reaches every display that shows one of the chosen screens, and **Pick Both** reaches either. You can pick up to 500 terminals and 500 screens. A screen pick follows the displays: a display moved to a picked screen starts showing the message, and one moved away stops. Only approved displays count, with or without a screen. The dialog says how many displays your choice reaches right now.

Several messages can run at once for different audiences. A display shows the newest one that reaches it. A display switched off by its display times stays off, and the preview of a picked screen shows the message as well. The list shows who sent each message, but a display never shows a name.

## Examples

**A fire drill.** You type Fire drill at **10:00**, pick Warning and Full Screen, choose **1 Hour** and keep **All Terminals**. Every display shows it within seconds.

**Hall 2 only.** You choose **Pick Infoscreens** and Hall 2 board, pick Banner and **End of Day**. The dialog says the message reaches three displays.

**Sent too early.** You click **End Now** next to the message, and the displays drop it at once.
