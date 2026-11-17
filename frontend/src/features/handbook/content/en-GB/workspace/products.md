---
title: Products
summary: How the product list and a product's page hold a machine's data, its projects, devices, sequences and documents, and who may change or archive a product.
sourceRefs:
  - backend/src/modules/workspace/domain/services/product_rules.py
  - backend/src/modules/workspace/domain/entities/product.py
  - backend/src/modules/workspace/application/use_cases/product/update_product.py
  - backend/src/modules/workspace/application/use_cases/product/archive_product.py
  - backend/src/modules/workspace/application/use_cases/product/restore_product.py
  - backend/src/modules/workspace/application/use_cases/product/get_renumber_impact.py
  - frontend/src/features/workspace/views/ProductDetailView.vue
lastVerified: 2026-11-10
---

Workspace, **Products** lists the machines you build. A product holds the machine's data for the CE assessment and its [projects](/handbook/workspace/projects), and, where those features are switched on, its devices, flow sequences, calculations and checklists. Active products also appear on the **Current products** widget of an infoscreen.

## The product list

The columns filter by number, customer, description, designated user, creation date and whether a product is **Active**, and the views bar sorts and groups by **Customer** or **Active Status**. A click on a row opens the product's page. **Create Product** needs **Write Projects**, and the **Product Number** must match the **Product Number Pattern** under Settings, **Numbering**. The archive and restore buttons in the row need **Manage Projects**; without it they show disabled, and their tooltip names the permission. Archiving a product also makes it inactive, and restoring it does not make it active again. **Show Archived** lists archived products.

## Editing a product

A product is edited by its designated user or by anyone with **Manage Projects**; for everyone else **Edit Product** shows disabled, and its tooltip says why. Besides number, customer and description, the form holds the **Machine data for the CE assessment**, which the product's checklists take into their header, the **PLC environment** its tags are built for, and its **Disciplines**, which decide the plans a device rename names. **Legal basis** is preselected from **Planned placing on the market**. Pictures and documents go into the product's files once it is saved.

Changing the **Product Number** opens **Change Product Number** before saving. It lists the devices that are renamed, warns that CAD files named after the old number must be renamed in CAD, that released calculations, checklists and exported reports keep the old number, and that outside systems no longer find the product under it. **Change Number** saves.

## The product page

The **Overview** shows the details, the machine data and links to the related records. **Projects** lists the product's projects, and **Bill of Material**, **Orders** and **Costs** add up all of them. **Files** appears while file storage is on. **Devices**, **Sequences**, **Calculations** and **Checklists** appear while those features are on; see [Product Devices](/handbook/workspace/product-devices), [Flow Sequences](/handbook/workspace/flow-sequences) and [Revisions and Release](/handbook/workspace/document-revisions). An archived product's devices and sequences can no longer change.

## Examples

**A new machine type.** You create product M-2045 for a customer, tick pneumatics and electrics under **Disciplines**, and then add its first project.

**A number typed wrong.** M-2054 should be M-2045. **Change Product Number** shows that twelve device names change with it, and you rename the CAD files that carry the old number.

**A machine no longer built.** Someone with **Manage Projects** archives the product. It drops out of the list and off the infoscreens, and **Show Archived** still finds it.
