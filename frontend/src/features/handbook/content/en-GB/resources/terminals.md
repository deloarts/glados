---
title: Terminals
summary: How a wall display is set up, approved, placed and looked after, alone or all at once, and what its details tell you.
sourceRefs:
  - backend/src/modules/operations/domain/services/terminal_rules.py
  - backend/src/modules/operations/domain/value_objects/terminal.py
  - backend/src/modules/operations/domain/value_objects/terminal_device_details.py
  - backend/src/modules/operations/application/use_cases/terminal/create_terminal_key.py
  - backend/src/modules/operations/application/use_cases/terminal/terminal_admin.py
  - backend/src/modules/operations/application/use_cases/terminal/terminal_bulk.py
lastVerified: 2026-11-10
---

A terminal is a TV on a Raspberry Pi running glados-terminal that shows one infoscreen. Under Resources, **Terminals** the table lists the displays in use. Anyone can look at the list and the details. Every other action needs **Manage Terminals**, and without it the buttons show disabled with a tooltip.

## Setting up a new display {#setup}

Create a terminal key under Settings, **API Keys**. Put the key into the settings of glados-terminal on the Pi and start it. The TV shows a six character pairing code, and the count on **Waiting for Approval** goes up. Approve the display with that code and pick its screen, and the TV switches within a few seconds.

## The terminal key {#terminal-key}

Click **Create Terminal Key** and give the key a **Name** and a date in **Expires On**, which is required while the Security tab limits token lifetimes. Glados shows the key only once. One key lets any number of new displays register, and an approved display keeps working when its key expires or is revoked.

## Approving a display {#approve}

**Waiting for Approval** lists the displays waiting for their code. Click **Approve** and type the **Pairing Code** from the TV, which proves that you stand in front of the right screen, and give it a **Name**. **Location** and **Screen** are optional. A code is valid for one hour, and at most twenty displays can wait at once.

## Looking after a display

Right click a display for its actions, or turn on **Show Actions** under **Views** to get them as buttons. **Edit Name and Location** and **Change Screen** take effect at once. **Reload** makes the TV load its page again, and **Identify** shows its name and location for a few seconds. **Switch Display Off or On** overrides the [Display Times](/handbook/resources/display-schedule#override) of its infoscreen, and the **Display** column shows whether the screen is on and until when. A display silent for five minutes is marked **Offline**. A short text for many displays at once is a [Message to Terminals](/handbook/resources/terminal-messages).

## Details of a display {#details}

Click a row or **Details** to see what the display reported about its computer, system and monitor. **Under-voltage** points to a weak power supply. Addresses, serial numbers, the host name and the key fingerprint identify a device, so only people with **Manage Terminals** see them; for everyone else they show as **Hidden**.

## Revoking and deleting {#all}

**Revoke** stops a display at once, for example when it was stolen. If it keeps running it shows a new pairing code and needs a new approval. **Delete** removes the entry, and a display that still runs registers again as a new one.

**All Terminals** reloads, identifies or revokes every approved display, or deletes every entry, waiting and revoked ones included. Each confirm names how many displays it hits, and **Revoke All** and **Delete All** ask you to type that number first.

## Duplicate use and allowed addresses {#allowlist}

**Duplicate Use Detected** appears when the same display signs in from a second address while its first session is valid, which suggests a copied memory card. Revoke it if you do not know why. Under Settings, **Security**, **Terminals** turns all displays off and **Terminal Allowed IPs** limits their addresses. Behind a reverse proxy, forward the display's address first.

## Examples

**A new hall display.** The TV shows K7M2QX. You open **Waiting for Approval**, click **Approve**, type k7m2qx, name it Hall 1 entrance, type the location Hall 1, above gate 3 and pick Hall board.

**A display that keeps restarting.** Its details show **Under-voltage** as Yes, so you replace its power supply.
