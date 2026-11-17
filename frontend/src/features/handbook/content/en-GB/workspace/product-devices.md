---
title: Product Devices
summary: How the devices of a machine are named, described for the PLC and kept in the device list of a product.
sourceRefs:
  - backend/src/modules/workspace/domain/policies/product_device_naming.py
  - backend/src/modules/workspace/domain/policies/product_device_rules.py
  - backend/src/modules/workspace/application/use_cases/product_device/assembler.py
  - backend/src/modules/workspace/application/use_cases/product_device/devices.py
  - backend/src/modules/workspace/application/use_cases/product_device/images.py
lastVerified: 2026-11-10
---

The **Devices** tab of a product lists its devices: cylinders, grippers, axes and buttons, each a group of parts such as a cylinder with its valve and two sensors. Every plan of the machine uses these names. The views bar switches to the [Device Overview](/handbook/workspace/device-overview), [Device Completeness](/handbook/workspace/device-completeness) and the [PLC Tags](/handbook/workspace/plc-tags), and the [Device Lists](/handbook/resources/product-devices) hold what devices pick from.

## How a device name is built

A name is made of the **Location**, the **Name**, the letter of the **Driving Medium** and a **Number**: B01, Lift Cylinder, pneumatics with the letter P and number 1 give B01 Lift Cylinder P1. Leave **Number** on **Next free** and Glados takes the next one of that location, name and letter. The preview shows the name while you type, with its ASCII form, in which umlauts are spelled out and other special characters become underscores. The product number stays out of the name; **Show names with product number** adds it to the list.

A device of a kind without driving medium, such as a push button, has no letter, and the first one has no number either: B00 Start Button, then B00 Start Button 2.

## What the dialog holds

The **Kind** decides the positions a device can be in. **Initial Position** is where it starts, **On Energy Loss** and **On Energy Restoration** say what it does when the power goes and comes back, and **Monitoring Time** is how long the PLC waits before it reports a fault. **Own Position Labels**, **Travel Times** and **Technical Parameters** are optional; the travel times feed the estimated cycle time of the flow sequences. **Images** holds one picture under **Rendering** for the device and one under **Parent Assembly** for the assembly it sits in. Under **Components** you list the parts with their **Role**, **EPLAN Tag**, **Catalogue Item** and signals. An input signal says which position it confirms, an output which position it drives to, and both may carry an **Address**. **Calculations** lists the calculations that refer to the device.

## Devices that move together

When a second clamp cylinder hangs on the valve of the first, pick the first one under **Driven By**. The driven device keeps only its sensors, and a flow sequence moves the driver instead. A driver of another kind needs **Positions**, which say where the driven device goes for each of the driver's positions.

## Renaming a device

Changing location, name, driving medium or number renames the device. Glados asks first and names the plans that have to follow, picked from the product's **Disciplines**: the EPLAN plan, the PLC code, the pneumatics or hydraulics plan, the robot program and the CAD assembly name. The device's ticks under **Completeness** are taken away.

## The device list

A click on a row opens the device, and a right click also offers **Copy Name**, **Copy ASCII Name**, and **Archive** or **Restore**. **Show Archived** lists archived devices again. An icon marks a device that no flow sequence uses yet. Changing devices needs the rights to edit the product, held by its designated user and anyone with **Manage Projects**. Without them **New Device** shows disabled with a tooltip, and the dialog opens read only.

## Examples

**Two clamps on one valve.** B01 Clamp Cylinder P2 is driven by B01 Clamp Cylinder P1. It gets no valve of its own, and a sequence that closes the clamps moves P1.

**A rename late in the project.** Lift Cylinder becomes Lifting Cylinder. Glados lists EPLAN, the PLC code, the pneumatics plan and the CAD assembly, and the device needs its ticks again.
