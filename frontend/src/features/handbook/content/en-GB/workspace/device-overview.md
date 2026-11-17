---
title: Device Overview
summary: How you place the devices of a product on a picture of the machine seen from above, and find them there again.
sourceRefs:
  - frontend/src/features/product-devices/components/ProductDeviceOverview.vue
  - frontend/src/features/product-devices/components/DeviceOverviewCanvas.vue
  - frontend/src/features/product-devices/components/ProductDeviceOverviewList.vue
  - backend/src/modules/workspace/application/use_cases/product_device/images.py
lastVerified: 2026-11-10
---

**Overview** in the views bar of the **Devices** tab shows a picture of the machine seen from above, with a numbered marker for each device. It helps you find a device on the machine and shows which devices nobody has placed yet. A marker carries the device's number in the device list. How devices are named and described is on [Product Devices](/handbook/workspace/product-devices).

## The overview picture

**Upload Overview** loads a picture of the machine as PNG, JPG, WEBP or SVG, and **Replace Overview** swaps it for a new one. A marker keeps its place relative to the picture, so a new rendering with the same framing keeps every marker where it was. Changing the overview needs the rights to edit the product, held by its designated user and by anyone with **Manage Projects**. Without them the buttons show disabled with a tooltip. An archived product's overview cannot change.

## Moving around

Scroll to zoom around the pointer and drag to move the picture. **Zoom in**, **Zoom out** and **Fit to view** do the same with buttons, and the keys plus, minus and zero work too. **Dot grid** switches the grid behind the picture on and off.

## Placing a device

Pick the device under **Pick a device to place**, or click it in the list beside the picture, and then click the picture where the device sits. The marker is saved at once. Picking a device that already has a marker brings it into view, and a click elsewhere moves it there. **Remove Marker** takes the marker off again. Without the rights to edit, the picker reads **Find a device** and only brings markers into view.

## The device list

The **Devices** panel beside the picture lists every device with its number. A crossed out marker icon means the device is not placed yet. The eye button hides one marker for this visit, and **Hide all** and **Show all** do it for every marker; a picked device always shows its marker. Pointing at a device highlights its marker together with the devices it moves with. **Hide detailed** turns off the small cards with name, type and rendering at each marker, which helps on a crowded picture. Drag the edge of the panel to make it wider.

## Examples

**A new machine.** You upload the layout exported from CAD as an SVG, pick B01 Lift Cylinder P1 and click where it sits. You repeat that for each device until the list shows no crossed out marker.

**A changed layout.** After a design change you click **Replace Overview** and pick a new rendering of the same view. Every marker keeps its place, and you move only the devices that changed.

**Finding a sensor on site.** A fitter without the rights to edit types the device name into **Find a device**, and the picture brings its marker into view.
