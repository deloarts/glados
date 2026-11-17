---
title: Device Completeness
summary: How the Completeness view tracks which plans of the machine already show each device, and which devices no flow sequence uses yet.
sourceRefs:
  - backend/src/modules/workspace/application/use_cases/product_device/completeness.py
  - backend/src/modules/workspace/domain/value_objects/device_plan.py
  - frontend/src/features/product-devices/components/ProductDeviceCompletenessTable.vue
lastVerified: 2026-11-10
---

**Completeness** in the views bar of the **Devices** tab shows one row per device and one tick per plan the machine needs. It answers whether every plan already carries the current device names before the machine is built and commissioned. How devices are named and renamed is on [Product Devices](/handbook/workspace/product-devices).

## Which plans count

The **CAD assembly** column is always there. **EPLAN**, **Pneumatics plan**, **Hydraulics plan** and **Robot program** follow the **Disciplines** ticked in the product's form: electrics, pneumatics, hydraulics and robotics. Change the disciplines and the columns follow, so a machine without hydraulics never asks for a hydraulics plan.

## Ticking a plan

Tick a plan once the device is drawn in it under its current name. Hover a tick to see who set it and when. A device with every tick shows a green check mark beside its name, and **Only Incomplete** hides those devices so the list shows what is still open. Renaming a device takes all its ticks away, because every plan has to show the new name again. Ticking needs the rights to edit the product, held by its designated user and by anyone with **Manage Projects**. Without them the boxes show disabled, and the tooltip says so.

## The flow sequence column

**Flow sequence** says whether a released revision of a flow sequence moves or checks the device (**Released**), only a draft does (**Only in drafts**) or none does (**In none**). A revision marked invalid does not count. A driven device counts through its driver, since a sequence moves the driver. The column shows only while flow sequences are switched on.

## Examples

**Before the electrical review.** The machine has pneumatics and electrics. The designer ticks **EPLAN** for each device the electrical plan shows, then turns on **Only Incomplete** to see which devices are still missing from a plan.

**A rename after the plans were drawn.** B01 Lift Cylinder P1 becomes B01 Lifting Cylinder P1. Its ticks disappear, the device shows up under **Only Incomplete** again, and each plan is ticked anew once it shows the new name.

**A device no sequence uses.** A new part sensor reads **In none**. It is either missing from the automatic cycle or not needed, and the sequence designer checks which.
