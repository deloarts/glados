---
title: Device Lists
summary: The lists every product device picks from, and the PLC environments that name and export its tags.
sourceRefs:
  - backend/src/modules/workspace/domain/services/product_device_resource_rules.py
  - frontend/src/features/product-devices/views/ProductDeviceResourcesView.vue
  - backend/src/modules/workspace/domain/services/plc_environment_rules.py
  - backend/src/modules/workspace/application/use_cases/plc_environment/environments.py
  - backend/src/modules/workspace/application/use_cases/product_device_resource/options.py
  - backend/src/modules/workspace/application/use_cases/product_device_resource/kinds.py
lastVerified: 2026-11-10
---

Resources, **Product Devices** holds the lists that the devices of every product pick from. They are shared by all machines and archived instead of deleted, because existing devices and sequences refer to them. How a product's own devices are named and tracked is on [Product Devices](/handbook/workspace/product-devices).

## Working with the lists {#lists}

The tab shows only while **Devices** is switched on under Settings, **Features**. The switch above the table picks the list, and each list has its own New button, such as **New Kind**. Right click a row to edit, **Archive** or **Restore** it, and use **Show Archived** to list archived entries again.

Creating, editing, archiving and restoring entries needs **Write Device Lists**. Without it the buttons and menu entries show disabled, and a menu entry names the permission you are missing.

If you may edit the lists, drag a row by the grip in its first column to reorder it. The pickers in the device form and the sequence editor offer the entries in this order for every user, so put the ones used most at the top. PLC environments have no order.

## Driving media

A driving medium, such as Pneumatics or Electrics, has a label and a **Letter** of one to four capitals that goes into every device name. Once a device uses it, the letter cannot change, since every plan would carry the old one.

## Device kinds and positions

A kind, such as Cylinder or Vacuum gripper, lists the **Positions** its devices can be in, the **Signals** they usually have besides them, such as a fault input, and their **Technical Parameters**. A position that **Takes a value**, such as an axis position in mm, gets its value in the sequence. **PLC state** and **PLC command** are optional; they end the tags of the inputs that confirm the position and of the outputs that drive to it, such as Ausgefahren and Ausfahren. Tick **Without driving medium** for operator devices such as buttons and key switches, whose names carry no letter.

## Component roles, energy behaviours and sequence names

**Component Roles** are the parts a device can have, such as valve or sensor. **Energy Behaviours** answer what a device does when its energy is lost or comes back. **Sequence Names** are proposed when a flow sequence is created; a sequence keeps its name as free text.

## PLC environments {#plc-environments}

A PLC environment, such as Siemens TIA Portal, says how the tags of a machine are named and exported. **Prefixes** set the start of a tag per signal type, with separate ones for safety signals. **Character Conversion** turns the device name into a valid tag. **Maximum Tag Length** is where the warnings start. **Tag Table**, **Safety Tag Table**, **Sheet Name** and the export columns shape the Excel file. A product picks its environment in its form; products without one use the environment marked **Default**.

To move an environment to another installation, open it and use the buttons at the bottom of the dialog. **Export to file** saves the form to a Glados template file. **Import from file** fills the form from such a file and lists any values it did not use. The import leaves the **Default** tick as it was and takes effect only when you click **Save**.

## Examples

**A new kind.** You create Linear axis with the positions Home and Position, the second taking a value in mm, with the PLC command Fahren. Every axis device then offers both positions, and its output tag ends in Fahren.

**A second PLC brand.** You copy the idea of the TIA environment into a new one with other prefixes and a shorter **Maximum Tag Length**, and pick it on the products built for that customer.
