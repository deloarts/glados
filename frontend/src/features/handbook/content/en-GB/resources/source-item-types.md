---
title: Source Item Types
summary: What a source item type is, how its name is kept in every language, and how the order of the list decides what the type picker offers first.
sourceRefs:
  - backend/src/modules/catalogue/domain/services/source_item_type_rules.py
  - backend/src/modules/catalogue/domain/services/label_name_rules.py
  - backend/src/modules/catalogue/application/services/labeled_entity_crud.py
  - backend/src/modules/catalogue/application/services/catalogue_list_order.py
lastVerified: 2026-11-10
---

A source item type is the kind of raw material block, such as round bar, flat bar or plate. Every source item has one, and together with its dimension and material the type tells source items apart. The list lives under Resources, **Source Item Types**. Entries are archived, never deleted, so source items keep their type.

## Name and description in every language

**Name** and **Description** have one input per language the application offers. The name needs a text in the default language, which comes first, and the other languages are optional. A language you leave empty shows the default language's name. A name has up to 200 characters and a description up to 4000.

Two types that are not archived may not show the same name in the same language. Upper and lower case and spaces around the name do not count, so Round bar and round bar clash. A German name may still equal the English name of another type.

## Colours

**Label Color** is the tag's background and **Font Color** its text, and **Preview** shows the result. A new type starts with grey and black.

## Permissions and archiving

Creating, editing, moving, archiving and restoring a type needs the permission **Write Source Item Types**. Without it the buttons show disabled. A restore is refused when a live type now uses its name in any language. Archived types stay on their source items, and the type picker lists them last with an **Archived** tag.

## The order of the list

The order of the table is the order the type picker offers, so put the types used most at the top. If you may edit source item types, the first column shows a grip in every row. Hold the grip and drag the row to its new place; a line shows where it will land. The grip shows only while no sort, search or filter is active, since those show the rows in another order. Showing archived types does not hide it. A new type goes to the end of the list.

## Where source item types are used

You choose the type under **Type** when you create or edit a source item, and the source items table and the details of a source item show it. The SolidWorks add-in gets each name in the language chosen as **Add-in Language** in the SolidWorks PDM settings.

## Examples

**A new type.** You create a type with Rundmaterial for German and Round bar for English. It is offered at once under **Type** in the source item form, at the end of the list.

**A type you no longer buy.** You archive Flat bar. Source items that have it keep it, and the type picker shows it last with an **Archived** tag. Restoring it later is refused if a live type is named Flat bar by then.

**Moving a type up.** Most of your blocks are round bar, so you hold the grip of Round bar and drag it to the top. The source item form now offers it first.
