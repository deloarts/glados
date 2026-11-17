---
title: Infoscreen Pages and Widgets
summary: How the pages of an infoscreen are laid out, what its header and footer hold and what each widget shows.
sourceRefs:
  - backend/src/modules/operations/domain/value_objects/infoscreen.py
  - backend/src/modules/operations/domain/services/infoscreen_rules.py
  - backend/src/modules/operations/application/use_cases/infoscreen/get_infoscreen_feed.py
  - backend/src/read/application/use_cases/infoscreen/build_infoscreen_feed.py
lastVerified: 2026-11-10
---

What an [infoscreen](/handbook/resources/infoscreens) shows is set in its editor, which opens from **Edit** on a row under Resources, **Infoscreens**. There, **Header and Footer** sets the bars around the pages and **Pages** sets what each page shows. Changing them needs **Write Infoscreens**; without it the editor only shows the screen.

## Header and footer {#bars}

**Show header** puts a bar above the pages and is on for a new screen; **Show footer** puts one below them and is off. Each bar has three areas, **Left**, **Middle** and **Right**. An area holds items such as the logo, the screen name, the clock, the date, the next holiday or a custom text. Add an item from the list under an area and move it with the arrows. Each item can be used once per bar, and the custom text needs its text. A new screen has the logo and the name on the left and the clock on the right.

## Pages and layouts {#pages}

Each page has a **Layout** with one to six positions, from Full screen with one widget to the two grids of six. Grid of six, upright suits a TV turned on its side. Pick a widget for every position, or leave it Empty. Changing the layout keeps the widgets that still fit and drops the rest. The arrows change the order of the pages, and a screen holds one to twenty pages.

## Widgets for the shop floor {#widgets}

Every widget can have a **Title**. The **Machine board** shows what runs on the chosen machines and on all machines of the chosen pools, followed by the **Upcoming Orders per Machine**, and adds a row for each pool with the orders that have no machine yet. The **Machine view** shows one **Machine** in full: the order on it now or the next one, with a large picture, the drawing if you tick **Show the drawing**, the item data and the orders that follow. **Lots due** lists the lots due within the **Days Ahead**, overdue ones first and marked late, and **Late lots** lists the lots past their date. Both hide customer names unless you tick **Show customer names**. **QA queue** shows what waits for inspection. **Deliveries expected** lists what should arrive within the days ahead, and with **Show overdue deliveries first** also what is late.

## Other widgets {#other-widgets}

**Current products** lists the active products, with their projects if you tick **Show the projects of each product**, and **Current projects** lists the active projects. **Weather** shows the weather now and for the **Days Ahead** in a town you pick by **Country** and **Place**. Only the town goes to the weather service, and an admin can switch the weather off under Settings, **Security**. **Message** shows your own text in a **Style** such as Warning, or None for plain text. It can use Markdown for bold, italic, headings and lists, and **Text Position** places it in one of nine spots. **Clock** shows the time as a **Digital**, **Analogue** or **Bit (binary)** clock, with the date, the next holiday and seconds if you like.

## Examples

**A hall board.** You create Hall board with the layout Main area and side bar, a Machine board for the milling pool in the main area and a Clock in the side bar. On the Terminals tab you give it to Hall 1 entrance.

**A screen at one machine.** You give a screen one page with the layout Full screen and a Machine view of the laser, and tick **Show the drawing**. The display beside the laser shows the drawing of the running order and what comes next.
