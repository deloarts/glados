---
title: Fabrication Methods
summary: What a fabrication method is, what each of its settings changes in planning and ordering, and how the list order works.
sourceRefs:
  - backend/src/modules/catalogue/application/use_cases/fabrication_method/update_fabrication_method.py
  - backend/src/modules/catalogue/application/use_cases/fabrication_method/_assembly_default.py
  - backend/src/modules/catalogue/domain/services/fabrication_method_rules.py
  - backend/src/modules/catalogue/domain/services/label_name_rules.py
  - backend/src/modules/catalogue/application/services/catalogue_list_order.py
lastVerified: 2026-11-10
---

A fabrication method is a kind of work a made item goes through, such as laser cutting, turning, welding or assembly. The steps of an item's process each use one method, machines list the methods they can do, and the schedule uses them to decide which machine can take an order. The list lives under Resources, **Fabrication Methods**.

## Name, description and colours

Each method has a **Name** and a **Description** in every language of the interface. The name is required in the default language and can be up to 200 characters long. No two methods that are not archived may show the same name in the same language, ignoring upper and lower case. **Label Color** and **Font Color** set how the method appears as a label, and **Preview** shows the result.

## Machine or manual work

**Requires a machine** is ticked for new methods. Untick it for pure manual work such as deburring by hand. A step with such a method never gets a machine or pool and is scheduled on the default calendar.

**Typically outsourced** marks work you usually send to a supplier. It is only a hint: you can still assign such a step to an internal machine, and the screen warns you when you do. Once it is ticked, **Lead time (days)** appears. It is optional and forecasts in calendar days when the work comes back. When it is empty, the **Default External Lead Time (days)** of the production settings is used, and a supplier with a lead time of its own always wins. **Default supplier** is optional too and fills in the supplier when you create an order for a step with this method.

## Default for assemblies

**Default for assemblies** marks the method the SolidWorks add-in preselects when it builds the process of an assembly. Only one method can hold it, so ticking it here takes it away from the method that had it. An archived method cannot hold it, and archiving the method that holds it leaves no default.

## Managing the list

You need the permission **Write Fabrication Methods** to create, edit, move, archive and restore methods. Without it the buttons show disabled. Methods are archived, not deleted, so existing steps keep theirs. **Show Archived** lists them again, and restoring is refused while a live method already uses the same name. In the table, **Machine** shows Manual for manual work, and **Flags** shows External, Assembly default and Archived. Saving a change replans the schedule, because lead times date the external steps.

The order of the list is the order the pickers offer. If you may edit fabrication methods, the first column shows a grip in every row. Hold the grip and drag the row to its new place; a line shows where it will land. The grip shows only while no sort, search or filter is active, since those show the rows in another order. New methods go to the end.

## Examples

**A machine method.** Create Laser cutting with **Requires a machine** ticked, then add it to the capabilities of your laser. Steps with this method can now be planned on that machine.

**Outsourced coating.** Create Powder coating, tick **Typically outsourced**, enter 10 in **Lead time (days)** and choose your coater as **Default supplier**. A coating step is expected back ten days after it goes out, and its order starts with that supplier.

**Assembly by hand.** Create Assembly, untick **Requires a machine** and tick **Default for assemblies**. The add-in now preselects it for assemblies, and those steps are planned without a machine.
