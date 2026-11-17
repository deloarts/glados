---
title: Article Groups
summary: How article groups classify your items, how their names are kept in every language, and how their order decides what pickers offer first.
sourceRefs:
  - backend/src/modules/catalogue/domain/services/article_group_rules.py
  - backend/src/modules/catalogue/domain/services/label_name_rules.py
  - backend/src/modules/catalogue/application/services/labeled_entity_crud.py
  - backend/src/modules/catalogue/application/services/catalogue_list_order.py
lastVerified: 2026-11-10
---

Article groups are your own purchasing classification, such as pneumatics, fasteners or sheet metal. An item can belong to several of them, and each group shows as a coloured tag on the item. The list lives under Resources, **Article Groups**. Entries are archived, never deleted, so items keep their groups.

## Name and description in every language

**Name** and **Description** have one input per language the application offers. The name needs a text in the default language, which comes first, and the other languages are optional. A language you leave empty shows the default language's name. A name has up to 200 characters and a description up to 4000.

Two groups that are not archived may not show the same name in the same language. Upper and lower case and spaces around the name do not count, so Pneumatics and pneumatics clash. A German name may still equal the English name of another group.

## Colours

**Label Color** is the tag's background and **Font Color** its text, and **Preview** shows the result. A new group starts with grey and black. When the pair is hard to read, the form says "This colour pair is hard to read at tag size." and offers **Use a readable font colour**, which sets the font colour to black or white, whichever reads better on the label.

## Permissions and archiving

Creating, editing, moving, archiving and restoring a group needs the permission **Write Article Groups**. Without it the buttons show disabled. A restore is refused when a live group now uses its name in any language. Archived groups stay on their items, and pickers list them last with an **Archived** tag.

## The order of the list

The order of the table is the order the pickers offer, so put the groups used most at the top. If you may edit article groups, the first column shows a grip in every row. Hold the grip and drag the row to its new place; a line shows where it will land. The grip shows only while no sort, search or filter is active, since those show the rows in another order. Showing archived groups does not hide it. A new group goes to the end of the list.

## Where article groups are used

You set article groups on bought items and made items, and on a supplier to record what it delivers. **Default article groups** in the EPLAN Data Portal settings are given to every item created from the portal. The SolidWorks add-in gets each name in the language chosen as **Add-in Language** in the SolidWorks PDM settings.

## Examples

**A new group.** You create a group with Pneumatik for German and Pneumatics for English, with a blue label and white font. German users see Pneumatik on their items, English users Pneumatics.

**A duplicate name.** A colleague names a new group pneumatics in English. The save is refused, since a live group already shows that name in English, whatever the case.

**Moving a group up.** The table is sorted by name, so no grip shows. You click **Sort by** to drop the sort, hold the grip of Pneumatics and drag it to the top. From now on the item forms offer it first.
