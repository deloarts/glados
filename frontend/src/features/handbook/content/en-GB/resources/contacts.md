---
title: Contacts
summary: How the people of customers and suppliers are kept as contacts, which mails reach them, how products and projects link them for the meeting notes, and how a contact is anonymised.
sourceRefs:
  - frontend/src/features/contacts/views/ContactManagementView.vue
  - frontend/src/features/contacts/components/ContactFormDialog.vue
  - frontend/src/features/contacts/components/ContactLinksSection.vue
  - backend/src/modules/catalogue/domain/services/contact_rules.py
  - backend/src/modules/catalogue/application/use_cases/contact/anonymise_contact.py
  - backend/src/modules/workspace/domain/services/contact_link_rules.py
lastVerified: 2026-11-10
---

A contact is a person you deal with: the project manager of a customer, the sales clerk of a supplier, or someone independent such as an inspector. Resources, **Contacts** lists them all with name and role, e-mail, phone, organisation and where they are used. Contacts are personal data, so reading them needs the permission **Read Contacts** and changing them **Write Contacts**. Without the right to change them the buttons stay visible but disabled.

## Creating a contact

**New Contact** opens the form. Only **Name** is required. **Role**, **E-Mail**, **Phone**, **Mobile** and **Note** are optional. **Belongs To** ties the contact to at most one customer or one supplier, or to neither. The customer and supplier forms have a **Contacts** section that lists and creates their people, once the customer or supplier is saved.

**Group by** **Organisation** groups the table by customer and supplier, and **Show Archived** shows the archived contacts too.

## Supplier mails

A supplier's contact can be ticked **Receives Request Mails** and **Receives Order Mails**. The supplier's quote requests and order mails then go to the ticked contacts. While no contact of a supplier is ticked, they go to the supplier's own addresses.

## Products, projects and the meeting notes

The overview of a product and of a project has a **Contacts** section. **Link Contact** adds one, with the contacts of the record's customer offered first, and **Meeting Notes** says whether the contact receives the meeting notes, which the send then suggests and ticks. Every project of a product inherits the product's contacts. A project cannot unlink an inherited contact, but it can untick **Meeting Notes** for itself, which mutes the contact for this project only. Linking follows the right to edit the product or project.

## Archiving and anonymising

A contact is archived, never deleted. An archived contact stays on every product, project and meeting that names it but is no longer offered for new ones. **Unarchive** in the contact form, or **Restore** in the table, brings it back.

When a person asks to be forgotten, **Anonymise** in the contact form removes the name, e-mail address, phone numbers and note for good and archives the contact. The same details are removed from the meetings that list the person as an attendee or todo owner and from the snapshots of sent notes, while the record that the notes went out stays. Anonymising needs **Write Contacts** together with **Manage Meetings** and cannot be undone.

## Examples

**The customer's project manager.** You create Eva Bogus, role Project Manager, belonging to the customer Acme Maschinenbau, and link her on the product with **Meeting Notes** ticked. Every project of the product now suggests her when its notes are sent.

**One project without her.** On a project of that product you untick **Meeting Notes** for Eva. Its meeting notes no longer suggest her, while the other projects still do.

**A new order clerk.** At the supplier you tick **Receives Order Mails** for the new clerk. The next order mail fills To with the clerk instead of the supplier's order address.
