---
title: Printers
summary: How to add a label or document printer, check that it works, take it out of use and see what it printed.
sourceRefs:
  - backend/src/modules/quality/application/use_cases/printer/create_printer.py
  - backend/src/modules/quality/application/use_cases/printer/test_print_printer.py
  - backend/src/modules/quality/application/use_cases/printer/get_printer_status.py
  - backend/src/modules/quality/domain/services/printer_rules.py
  - backend/src/modules/quality/application/use_cases/print_document/get_print_jobs.py
  - backend/src/modules/quality/domain/services/printer_host.py
lastVerified: 2026-11-10
---

Under Resources, **Printers** lists every printer Glados can send to.

## Label printers and document printers

**Kind** decides what a printer receives. A **ZPL Label** printer takes labels in the label printer language ZPL and is reached with the **Transport** **Raw (JetDirect)**, usually on port 9100. An **IPP Document** printer takes PDF files such as reports and dockets and is reached with **IPP**, usually on port 631. Changing **Kind** switches **Transport** and the usual port to match; a port you typed yourself stays.

## Adding a printer

Click **New Printer** and fill in **Name**, **Kind**, **Host** and **Port**, a number from 1 to 65535. The other fields are optional. **Host** is the printer's network name or address, and Glados refuses addresses of the server itself and of its own services. **Timeout (seconds)** is how long Glados waits for an answer, 5 by default.

For a label printer, **Head DPI** is the resolution of its print head, 300 by default. **Format Convert Factor** must match the format convert setting on the printer's own panel; a wrong value prints labels at the wrong size. For a document printer, **IPP URI Path** starts at "/" and **Default Media** names the paper the printer uses unless told otherwise.

**Location**, **Vendor**, **Model**, **Firmware** and **Note** only describe the printer. **Consumables** lists the bought items it uses up, such as labels, ribbon or toner.

## Enabled and archived printers

A printer that is not **Enabled**, or that is archived, receives nothing. Labels and dockets meant for it are not sent; they show up as failed in its **Print History** with the reason. Switch **Enabled** off while a printer is being repaired, and archive it once it is gone for good. **Disable All Printers** on the **Print Labels** and **Print Dockets** pages switches every printer off at once.

## Checking a printer

**Test Print** sends a small test label or a one page PDF with your user name and the time. It also reaches a disabled printer, so you can check a new printer before you enable it. **Printer Status** asks the printer how it is and shows its **Identity** and **Status**, or "Could not reach the printer." when it does not answer. An answer that does not come from a label printer is not shown, and the status says so.

With **Show Actions** on, each row has buttons for both checks, **Edit Printer** and **Archive** or **Restore**. A right click on a row offers the same actions and **Print History**. The table can be grouped by **Kind** or **Location**.

## Print History {#history}

**Print History** lists what was sent to the printer with **Created**, **Document**, **Record**, **Trigger**, **Copies**, **Status** and **Actor**. **Trigger** says whether the print was **Auto** or **Manual**, and **Status** is **Printing**, **Sent** or **Failed**; point at a failed status to read why. Printing reports is covered in [Exporting and Printing Reports](/handbook/resources/report-export).

## Who can do what

Adding, editing, archiving and restoring a printer needs **Write Printers and Templates**. **Test Print** and **Printer Status** need **Print Documents**, and **Print History** needs **Read Settings**. Without them **New Printer**, **Edit Printer**, **Test Print**, **Printer Status**, **Print History**, **Archive** and **Restore** show disabled with a tooltip that names the missing permission.

## Examples

**A new label printer.** Click **New Printer**, enter Zebra hall 2, choose **ZPL Label**, enter its address and keep port 9100. Switch **Enabled** off, click **Test Print**, check the size of the label, then switch **Enabled** on.

**A printer in repair.** Switch **Enabled** off for the office printer. The lot dockets meant for it are not printed and appear as **Failed** in its **Print History**, so you can print them again once it is back.
