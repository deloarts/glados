---
title: Print Dockets
summary: What a docket is, how it differs from a label in setup, which paper it prints on and where it is printed or downloaded.
sourceRefs:
  - backend/src/modules/quality/application/use_cases/print_document/download_print_document.py
  - backend/src/modules/quality/application/services/docket_spec.py
  - backend/src/modules/quality/application/use_cases/print_template/update_print_template.py
  - backend/src/modules/quality/application/use_cases/print_template/reset_print_template.py
  - backend/src/modules/quality/application/use_cases/print_template/preview_print_template.py
  - backend/src/modules/quality/domain/services/print_template_rules.py
  - backend/src/modules/quality/application/use_cases/print_document/print_document.py
  - backend/src/modules/quality/application/use_cases/print_document/handle_event_auto_print.py
lastVerified: 2026-11-10
---

A docket is a PDF travel sheet that goes with the work through the shop, printed on a document printer or downloaded. Under Resources, **Print Dockets** holds one fixed row per kind: **Order Docket**, **Lot Docket**, **Production Order Docket**, **Made Item Docket**, **Bought Item Docket** and **Source Item Docket**. You cannot create or delete a row, only set it up.

## How a docket differs from a label

**Edit Docket** opens the same editor as for labels, described in [Print Labels](/handbook/resources/print-labels), with a few differences. **Printer** offers only document printers. **Copies Rule** is always **Fixed**, so a docket prints **Fixed Copies**, never more than **Max Copies**. The **Order Docket** has no event to print on and is always printed by hand.

The content is a layout rather than a label: **Block Spec (JSON)** describes the blocks of the page, and the editor warns at once when it is not valid JSON. **Field Map** links every field the layout names to a piece of the docket's data. Saving checks the same things as for a label, and that the printer is a document printer.

## Paper {#paper}

**Paper** decides how the docket lands on the sheet. **A4 (centred with cut marks)** puts the docket in the middle of an A4 page with marks to cut along. **A4 aligned (cut in half for an A5 docket)** places it so that cutting the page in half gives an A5 docket. **A5 (1:1)** prints it at its own size on A5 paper. The table shows the choice under **Page Size**.

## Preview and download

Enter a **Record ID** in the preview pane to see the docket for a real record. **Download PDF** next to it saves the docket as a file instead of printing it, which only works while the docket is enabled and has content. A download involves no printer, so it does not appear in any **Print History**.

## Where dockets are printed

On an item's page, **Print** and **Docket** print the item's docket. In the lots table, **Print** offers **Print Lot Docket**, and the lot page prints it with **Print Docket**. Production queue cards and the machine page print the production order's docket with **Print Docket**. In the orders table, a right-click offers **Download Docket** to save the order docket and **Print Docket** to send it to its printer.

Automatic printing, failed prints and **Disable Auto-Print** work as for labels: a failed docket never blocks the work and shows as **Failed** in the printer's **Print History**.

## Who can do what

Editing and **Clear Content** need **Write Printers and Templates**. **Preview**, **Test Print**, downloading and printing need **Print Documents**. Without them **Edit Docket**, **Clear Content** and **Test Print** show disabled.

## Examples

**A lot docket with every new lot.** Choose **Lot created** as **Trigger**, the office printer and **A4 aligned (cut in half for an A5 docket)**, then switch on **Auto-print**. Every new lot prints one docket, and cutting the page in half gives the A5 sheet that travels with the parts.

**An order docket as a file.** Right-click the order in the orders table and choose **Download Docket**. The PDF is saved on your computer, ready to print or file with the order.

**A broken layout.** You paste a block spec with a missing bracket. The editor shows that it is not valid JSON, and saving stays refused until it is fixed.
