---
title: Infoscreens
summary: How a screen for the wall displays is created, in which language it speaks, and how it is previewed and archived.
sourceRefs:
  - backend/src/modules/operations/domain/services/infoscreen_rules.py
  - backend/src/read/application/use_cases/infoscreen/build_infoscreen_feed.py
  - backend/src/modules/operations/domain/value_objects/infoscreen.py
  - backend/src/modules/operations/application/use_cases/infoscreen/get_infoscreen_feed.py
lastVerified: 2026-11-10
---

An infoscreen is what a wall display shows: a set of pages that the TV turns through by itself. You build screens under Resources, **Infoscreens**, and you give a screen to a display on the **Terminals** tab. One screen can run on many displays, and the **Shown On** column lists them. Anyone can look at screens and their preview. Creating, editing and archiving need **Write Infoscreens**, and without it the buttons show disabled with a tooltip. The pages, bars and widgets of a screen are explained in [Infoscreen Pages and Widgets](/handbook/resources/infoscreen-pages).

## The look of a screen

Click **New Infoscreen** and give it a **Name**. The **Description** is optional. **Colour Mode** is Dark unless you choose Light, which suits bright offices. **Theme** and **Primary Colour** are optional; without them the screen uses the default of this installation. **Page Time (seconds)** sets how long each page stays, between 10 and 600 seconds. **Show the banner of this installation** adds the banner that every user sees, for announcements that concern everyone. **Display Times** sets when the displays showing the screen switch off, as [Display Times](/handbook/resources/display-schedule) explains. **Display Schedule** in the row's menu sets the same times without opening the editor, and the **Schedule** column sums them up.

## Language {#language}

The **Language** is optional and decides the words the screen writes itself, such as dates, weekdays, default widget titles and the labels in the bars. With **Default of this installation** the screen follows the default language under the general settings, and the **Language** column shows which one that is today, for example Default of this installation (English). Texts you type, such as titles, the custom text and messages, stay as you typed them. The preview shows the screen in its language.

## No names on the screen

A screen never shows the names of people, such as operators or the person who ordered something. Customer names are hidden unless you tick **Show customer names** on the widgets Lots due or Late lots, since even company names can be confidential in a visitor area.

## Preview and archive

Right click a row for **Edit**, **Preview**, **Display Schedule** and **Archive** or **Restore**. The same actions show as buttons in each row once you turn on **Show Actions** under **Views**. **Preview** opens the last saved version in a new tab, exactly as a TV shows it, so save first to see your changes. **Archive** takes a screen out of the list and out of the choice on the Terminals tab, so give the displays that show it another screen first. **Show Archived** lists archived screens again, and **Restore** brings one back.

## Examples

**A screen for the office.** You create Office board, choose Light and a **Page Time (seconds)** of 60, and add the widgets Lots due and Deliveries expected. On the Terminals tab you give it to the display in the office.

**A screen in German.** The installation speaks English, but the hall team reads German. You set the **Language** to Deutsch, and the dates and headings on the screen turn German while your message stays as typed.
