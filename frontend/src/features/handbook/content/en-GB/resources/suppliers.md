---
title: Suppliers
summary: How a supplier is set up for ordering, what its lead time and EPLAN Data Portal code do, and how its order and request mails are composed.
sourceRefs:
  - backend/src/modules/catalogue/domain/services/supplier_rules.py
  - backend/src/modules/catalogue/domain/services/supplier_edp_code.py
  - backend/src/modules/catalogue/application/use_cases/supplier/create_supplier.py
  - backend/src/modules/catalogue/application/use_cases/supplier/update_supplier.py
lastVerified: 2026-11-10
---

A supplier is a company you buy from or send work to, and it is also the manufacturer of your bought items. The list under Resources, **Suppliers** holds its details, its order mail settings and its link to the EPLAN Data Portal. Entries are archived, never deleted, so old orders keep their supplier.

## Creating and editing a supplier

**Create Supplier** opens the form. Only **Name** is required, and every other field is optional. **Legal Name**, the address and the contact details work as for customers, and **Level** rates the supplier A, B or C, starting at B. **VAT ID** is optional, but two suppliers that are not archived cannot share one. Creating and editing needs the permission **Write Suppliers**, and without it the buttons show disabled.

**Fabrication Methods** lists the work the supplier can do for you, and **Article Groups** what it delivers. The table shows both as **Fabrication Capabilities** and **Article Groups**, filters by them, and **Group by** groups it by **Country** or **Capability**.

## Lead time

**Lead time (days)** is optional and must be 0 or more. When it is set and a position of a production lot is ordered from this supplier, the schedule expects the work back after that many calendar days instead of the lead times of the position's steps. Changing it replans the schedule.

## EPLAN Data Portal

**EPLAN Data Portal code** is the portal's short name for the manufacturer, such as SIE for Siemens. Parts from the portal find their manufacturer by it. It has up to 16 characters, starts with a letter or digit and may then also hold underscores, dots and hyphens. It is saved in upper case, and only one live supplier may carry a code. Tick **Type number is order code 1** for a manufacturer whose type number is the one you order by.

## Order and request mails {#mails}

**Order Email**, **Order Language** and **Order Template** decide where an order mail goes, the language it is written in and its text. **Edit Template** opens an editor where you click a variable or a table column to insert it. Without a template the default from the settings is used, and without **Order Email** the mail goes to **Email**.

**Request Email**, **Request Language** and **Request Template** do the same for quote requests. Each one left empty takes the order setting instead.

The **Contacts** section of the supplier lists its people. A contact with **Order Mails** ticked receives the supplier's order mails, and one with **Request Mails** ticked its quote requests, so the mail fills **To** with them. Only when no contact is ticked does the mail go to the addresses above, so a supplier without contacts gets its mails there. [Contacts](/handbook/resources/contacts) explains them.

## Archiving and restoring

**Archive** and **Restore** sit in the row actions under **Show Actions** and in the right click menu, and both need the permission **Archive Suppliers**, so they show disabled without it. A restore is refused when another live supplier holds the same VAT ID in the meantime.

## Where suppliers are used

You pick suppliers as the manufacturer of bought items and source items, on orders and quote requests, when ordering demands, and as the default supplier of a fabrication method. The SolidWorks add-in reads them too.

## Examples

**Setting up Festo.** You create Festo, enter fes as the code and tick **Type number is order code 1**. The code is saved as FES, and a portal part such as DFM-25-50-P-A-GF arrives with that type number as order code 1 and the portal's order number 170851 as order code 2.

**An outsourced coating.** You set **Lead time (days)** of your coater to 10. A lot position ordered from it is now planned back 10 calendar days after ordering, whatever its steps say.

**A quote request.** A supplier has only **Order Email** and **Order Language** filled in. Its quote requests go to that address, in that language.
