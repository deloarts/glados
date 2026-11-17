---
title: PLC Tags
summary: How the PLC tags of a machine are built from its devices, how you correct and extend them, and how they are exported.
sourceRefs:
  - backend/src/modules/workspace/domain/services/plc_naming.py
  - backend/src/modules/workspace/application/use_cases/plc_environment/tags.py
  - backend/src/modules/workspace/domain/services/plc_environment_rules.py
lastVerified: 2026-11-10
---

**PLC Tags** in the **Devices** tab lists every tag of the machine, built from the signals of its devices, followed by the tags you add by hand. The list follows the devices, so a renamed device renames its tags at once, and the PLC programmer gets a table that matches the plans.

## How a tag is built

A tag starts with the prefix of its signal type, such as di_ for a digital input or dq_ for a digital output, and a safety signal takes the safety prefix of its type, such as fdi_. Then comes the device name, spelled out by the character conversion of the PLC environment, so ü becomes ue and spaces become underscores. The end is the signal's **Tag suffix** when it has one, else the PLC name of its position (the state name for an input, the command name for an output), else the **PLC name** of the kind signal it picks, such as a fault input, else the meaning of the signal. The PLC names of the positions and signals are set on the device kind. The product number is never part of a tag.

The product's **PLC environment** decides the prefixes, the conversion, the **Maximum Tag Length** and the export. Without a choice of its own, a product uses the default environment. How an environment is set up, and how it moves to another installation as a file, is on [Device Lists](/handbook/resources/product-devices#plc-environments).

## Notes in the list

**Too long** marks a tag longer than the environment allows; the device dialog already warns while you type the name. **Twice** marks a name that another tag of the machine has too, in any upper or lower case. **No address** marks a signal without a PLC address, and **Own name** a tag whose name you set yourself. None of them stops you; they show what still needs attention.

## Correcting and adding tags

Edit a built tag to give it a name of your own. The name is kept on the device's signal, so it moves with the device and the list never holds a copy that could drift. **Use Built Name** goes back to the built one. **Add Tag** adds a tag that belongs to no device, such as an HMI button or a signal from the robot, with its type, address and comment. A tag name holds only letters, digits and underscores.

## Export

**Export** writes the list as an Excel file in the columns of the environment, on the sheet it names, ready for the import of the PLC software. Safety signals go to the safety tag table when the environment has one.

## Examples

**A cylinder's sensor.** B01 Lift Cylinder P1 has an input that confirms Extended, whose PLC state is Extended. Its tag is di_B01_Lift_Cylinder_P1_Extended.

**An umlaut in the name.** The environment converts ü to ue, so the same input on B03 Drücker P1 becomes di_B03_Druecker_P1_Extended.

**An emergency stop with two channels.** Both inputs of B00 Emergency Stop confirm Pressed, so both become fdi_B00_Emergency_Stop_Pressed and are marked **Twice**. Give them the tag suffixes Channel1 and Channel2 and the marks disappear.

**A robot signal.** **Add Tag** with the name di_Robot_Ready, type DI and address I3.0 adds the robot's ready signal to the export.
