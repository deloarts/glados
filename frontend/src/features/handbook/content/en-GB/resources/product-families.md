---
title: Product Families
summary: What a product family is, how it differs from an article group, and how it is set on a bought item.
sourceRefs:
  - backend/src/modules/catalogue/application/use_cases/product_family/create_product_family.py
  - backend/src/modules/catalogue/domain/services/product_family_rules.py
  - backend/src/modules/catalogue/application/services/catalogue_list_order.py
  - backend/src/modules/catalogue/application/services/product_family_lookup.py
  - backend/src/modules/external_data/application/services/edp_item_draft.py
lastVerified: 2026-11-10
---

A product family is the manufacturer's kind of product, such as cylinders, valves or contactors. It helps you find all parts of one kind quickly in the bought items catalogue. Article groups are your own purchasing classification and an item can have several; a product family is the manufacturer's view, and an item has at most one.

## Managing the list

The list lives under Resources, **Product Families**. Each family has a **Name**, a **Description** and a **Label Color** with a **Font Color**, which is how it appears on items. When the pair is hard to read, the form says "This colour pair is hard to read at tag size." and offers **Use a readable font colour**, which picks black or white for the text. A name can be used by only one family that is not archived.

Product families have no permissions of their own. Creating, editing, moving, archiving and restoring a family needs **Write Article Groups**. Without it the buttons show disabled.

The order of the list is the order the pickers offer, so put the families used most at the top. If you may edit product families, the first column shows a grip in every row. Hold the grip and drag the row to its new place; a line shows where it will land. The grip shows only while no sort, search or filter is active, since those show the rows in another order. A new family goes to the end of the list.

## Setting it on an item

Choose the family in the item's form under **Product Family**. Archived families are not offered, but an item that already has one keeps it. The family can also be set on items that come from SolidWorks PDM. In the bought items catalogue the **Product Family** column shows it and filters by it.

## From the EPLAN Data Portal

When an item is filled from the EPLAN Data Portal, its family is the one named like the portal's product group, in any upper or lower case. A family that does not exist yet is not created; create it here and the next lookup finds it.

## Examples

**Grouping cylinders.** Create the family Cylinders and set it on your Festo cylinders. Filtering the catalogue by Cylinders now lists them all, whatever article groups they have.

**A renamed family.** You rename Cylinders to Pneumatic cylinders. Every item keeps it, since the item points to the family, not to its name.
