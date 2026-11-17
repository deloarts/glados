---
title: Customers
summary: How a customer is created and kept up to date, what its level and VAT ID mean, and where you pick it.
sourceRefs:
  - backend/src/modules/catalogue/domain/services/customer_rules.py
  - backend/src/modules/catalogue/application/use_cases/customer/create_customer.py
  - backend/src/modules/catalogue/application/use_cases/customer/update_customer.py
  - backend/src/modules/catalogue/application/use_cases/customer/restore_customer.py
lastVerified: 2026-11-10
---

A customer is the company you build machines for. Projects and products point to their customer, so the list under Resources, **Customers** is the one place for its name, address and contact details. Entries are archived, never deleted, so a customer you no longer serve still shows on its old projects.

## Creating and editing a customer

**Create Customer** opens the form. Only **Name** is required, and every other field is optional and can be filled in later. **Legal Name** is the registered company name when it differs from the short name you use every day. **Street**, **City**, **Postal Code** and **Country** make up the address, and you pick the country from a list. **Email**, **Phone** and **Website** are the contact details.

Creating and editing a customer needs the permission **Write Projects**. Without it the button stays visible but disabled. If someone else saved the same customer while you had the form open, your save is refused, so open the customer again and repeat your change.

The **Contacts** section of a saved customer lists its people and creates new ones with **New Contact**. They are the customer's contacts that the meeting notes of its projects and products can go to, see [Contacts](/handbook/resources/contacts).

## Level and VAT ID

**Level** rates the customer A, B or C, and a new customer starts at B. The table shows it as a coloured tag: A green, B blue and C red.

**VAT ID** is optional, and Glados does not check its format. It is what tells two companies apart, so two customers that are not archived cannot share one. The name may repeat, the VAT ID may not.

## Finding a customer

**Search**, the column filters and **Sort by** narrow and order the table, and **Group by** groups it by **Country** or **Level**. **Created** and **Changed** show the date and the person. Clicking a row opens the customer's details, read only. To edit a customer, turn on **Show Actions** and use the pencil of its row, or right click the row.

## Archiving and restoring

**Archive** hides the customer from the table, **Show Archived** shows it again, and **Restore** makes it live once more. Both need the permission **Manage Projects** and show disabled without it. A restore is refused when another live customer holds the same VAT ID in the meantime.

## Where customers are used

You pick the customer in the form of a project, of a product and of a new made item, and in the customer filter of the production KPIs. These pickers still offer archived customers, listed last with an **Archived** tag, so older records keep theirs. The global search finds the projects, products and production lots of a live customer when you type its name or legal name.

## Examples

**A new customer.** You enter Acme Maschinenbau with the VAT ID ATU12345678 and leave **Level** at B. It can be picked in the project form straight away.

**The same company twice.** A colleague creates Acme Maschinenbau GmbH with the VAT ID ATU12345678. The save is refused, since a live customer already holds that VAT ID, so the colleague opens the existing one instead.

**Bringing a customer back.** You archived an old customer, and later a new entry was created with its VAT ID. Restoring the old one is refused until the VAT ID of one of the two changes.
