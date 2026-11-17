---
title: Print Labels
summary: How each label is set up, when it prints by itself, what happens when a print fails and where labels are printed by hand.
sourceRefs:
  - backend/src/modules/quality/application/use_cases/print_template/update_print_template.py
  - backend/src/modules/quality/application/use_cases/print_template/reset_print_template.py
  - backend/src/modules/quality/application/use_cases/print_template/preview_print_template.py
  - backend/src/modules/quality/domain/services/print_template_rules.py
  - backend/src/modules/quality/domain/services/zpl_template.py
  - backend/src/modules/quality/application/use_cases/print_document/print_document.py
  - backend/src/modules/quality/application/use_cases/print_document/handle_event_auto_print.py
lastVerified: 2026-11-10
---

Under Resources, **Print Labels** holds one row per kind of label: **Source Item Label**, **Bought Item Label**, **Made Item Label**, **Production Order Label**, **Lot Label** and **Scrap Tag**. The rows are fixed; you only set each one up.

## Setting up a label {#setup}

Right-click a row and choose **Edit Label**. **Trigger** is **Manual only** or one of the events that fit this label. **Printer** offers only label printers; an archived one is listed last with a warning. **Auto-print** stays greyed out until a trigger is chosen, and a label that is not **Enabled** never prints.

**Copies Rule** decides how many copies one print makes. **Fixed** prints **Fixed Copies**. **Per occurrence quantity** prints one copy per piece delivered or completed, and **Per lot quantity** one per piece of the lot; each label offers only the rules that suit it. **Max Copies** caps any single print. A label printed by hand always makes **Fixed Copies**.

## The content

**ZPL Source** holds the label in the label printer language ZPL; type it in or **Upload** a .zpl or .txt file. Every name in curly braces is a placeholder, and **Field Map** links each one to a piece of this label's data, such as the part number. Enter a **Record ID** in the preview pane to see the label for a real record. **Import from file** and **Export to file** move a label between systems, and only an imported file sets the label size.

Saving checks that trigger and copies rule suit this label, every placeholder is mapped, the source is a complete label and the printer is a label printer. **Clear Content** empties the source, the field map and the size and switches the label off, but keeps its trigger, printer and **Auto-print**.

## Printing by itself

A label prints on its trigger event only when it is enabled, armed for **Auto-print** and has a printer. **Disable Auto-Print** disarms every label at once and leaves manual printing alone. **Disable All Printers** stops all printing.

## When a print fails

A failed print never blocks the work on the shop floor. The delivery, completion or scrap is recorded, and the print is logged as **Failed** in the printer's **Print History** with the reason. A print started by hand also shows the reason. The same happens when the label is disabled or empty, has no printer, or its printer is disabled or archived, see [Printers](/handbook/resources/printers).

## Where labels are printed

Right-click an item in a catalogue and choose **Print Label**, or use **Print** and **Label** on its page. In the lots table, **Print** offers **Print Lot Label** and **Scrap Tag**, and the lot page has both under **Print Docket** as **Print Lot Label** and **Print Scrap Tag**. **Scrap Pieces** offers **Print scrap tag**, ticked when the **Scrap Tag** has a printer. Production queue cards and the machine page offer **Print Label** and **Print Docket**.

## Who can do what

Editing and **Clear Content** need **Write Printers and Templates**. **Preview**, **Test Print** and printing need **Print Documents**. Without them **Edit Label**, **Clear Content** and **Test Print** show disabled. An automatic print needs no permission from the person whose action triggered it.

## Examples

**A lot label on every new lot.** Choose **Lot created** as **Trigger**, the hall printer, **Per lot quantity** and **Max Copies** 20, then switch on **Auto-print**. A lot of 12 pieces prints 12 labels; a lot of 50 prints 20.

**A delivery while the printer is off.** The **Bought Item Label** prints on **Bought item delivered**, but its printer is disabled. The delivery is booked anyway, and the print shows as **Failed** with the reason.
