---
title: EPLAN Data Portal
summary: How Glados fills bought items from the EPLAN Data Portal, when you create one and later on an existing item, and what happens to items PDM manages.
sourceRefs:
  - backend/src/modules/external_data/application/services/edp_item_draft.py
  - backend/src/modules/external_data/application/use_cases/eplan_data_portal/edp_lookup.py
  - backend/src/modules/external_data/application/use_cases/eplan_data_portal/fill_edp_picture.py
  - backend/src/modules/catalogue/domain/services/supplier_edp_code.py
  - backend/src/modules/external_data/domain/entities/admin_settings/eplan_data_portal.py
lastVerified: 2026-11-13
---

The EPLAN Data Portal is EPLAN's catalogue of manufacturer parts. When your administrator switched it on, Glados can fill a bought item from it: the article name, the order code and type number, the EAN, a link to the manufacturer's page, the manufacturer, the product family and the product picture. Mass, tariff number and price are not in the portal, so you still enter them yourself.

## Creating an item from the portal

In the create dialog, type an order code, a type, an EPLAN part number or a name into **Fill from the EPLAN Data Portal** and pick a part from the list. The fields below are filled and you can still change them before saving. If the part is already in the catalogue, the dialog says so, so you do not create it twice. The new item is linked to the part, and when file storage is on, its picture arrives a moment later. It gets the **Default article groups** of the Data Portal settings, and its article name is taken in the **Article name language** set there, or in the other language when the portal has none.

Searching the portal needs the permission **Use EPLAN Data Portal**, and saving the item still needs **Write Bought Items**. Without the first, the search field shows disabled and its tooltip names the permission, and part pictures show a placeholder. Looking up an existing item needs **Write Bought Items** only.

## Matching the manufacturer

A part only finds its manufacturer through the supplier's **EPLAN Data Portal code**, for example SIE for Siemens or FES for Festo. It is entered once in the supplier form. When no supplier has the code, Glados leaves the manufacturer empty and tells you which code is missing. Normally the portal's order number becomes **Order Code 1** and its type number **Order Code 2**. For a maker that orders by type number, such as Festo, tick **Type number is order code 1** on the supplier, and the two swap, for example DFM-25-50-P-A-GF as order code 1 and 170851 as order code 2.

## Looking up an existing item

On a bought item's page, **Lookup in Data Portal** finds the item's part by its link or its order code and compares them field by field. If the portal knows several parts by that number, choose one. Fields where the portal differs are ticked; the take button, for example **Take 2 fields**, writes the ticked ones, and **Only link** links the item without changing it. Either way the product picture becomes the item's Data Portal picture. It sits beside a photo someone uploaded and beside the CAD rendering from PDM, and replaces neither. The item shows a photo first, then the Data Portal picture, then the CAD rendering. Linking the item to another part brings that part's picture, and removing the link removes it.

## Items managed by PDM

For an item that comes from SolidWorks PDM, the fields PDM manages are shown but cannot be taken. Change them in the SolidWorks file, and they arrive with the next release. The product family and the link to the portal can still be set here.

## Examples

**A new contactor.** You type 3RT2015 and pick the Siemens contactor. Name, order codes, EAN, link and Siemens as manufacturer are filled, and the product family Contactors is set because it exists in Glados.

**An old item with a short name.** A web item is called "Contactor". The lookup shows the portal's full designation; you take only the article name.

**An item from PDM.** The lookup shows a different article name, but it cannot be ticked. The engineer corrects it in the SolidWorks file.
