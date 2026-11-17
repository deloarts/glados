---
title: Projects
summary: How the project list and a project's page show its demands, orders, costs and documents, and who may create, edit and delete a project.
sourceRefs:
  - backend/src/modules/workspace/domain/services/project_rules.py
  - backend/src/modules/workspace/domain/policies/project_activity.py
  - backend/src/modules/workspace/application/use_cases/project/create_project.py
  - backend/src/modules/workspace/application/use_cases/project/update_project.py
  - backend/src/modules/workspace/application/use_cases/project/delete_project.py
  - frontend/src/features/projects/components/ProjectFormDialog.vue
  - frontend/src/features/workspace/views/ProjectDetailView.vue
lastVerified: 2026-11-10
---

Workspace, **Projects** lists every project: a customer order to build a machine or a part of one, which demands, lots, orders, calculations and checklists belong to. A project usually belongs to a [product](/handbook/workspace/products), the machine it builds, and several projects can share one product. On a phone, Workspace offers only the projects, and a project only its overview.

## The project list

The columns filter by status, number, product, customer, description, delivery dates, designated user and creation date, and the views bar sorts and groups by **Customer** or **Status**. A click on a row opens the project's page. A right click offers **Project Details**, **Edit Project**, **Show Items** and **Delete**. **Show Items** lists the bought items of the project with **Qty Demanded** and **Qty Fulfilled**.

## Creating and editing a project

**Create Project** needs **Write Projects**. The **Project Number** must match the **Project Number Pattern** under Settings, **Numbering**. A **Product** is required unless **Allow Projects Without a Product** is on under Settings, **General**. The **Designated User** is you, and only someone with **Manage Projects** can pick another person. **Production Time Budget** is optional and gives planning the manufacturing minutes sold for the project. **Required Delivery Date (Made Items)** and **Required Delivery Date (Bought Items)** prefill new demands of the project. When you change one, Glados asks whether to **Apply to all** open demands or **Just this project**.

A project is edited by its designated user or by anyone with **Manage Projects**. For everyone else **Edit Project** shows disabled, and its tooltip says why. Changing the **Status** needs **Manage Projects**, and a status the project cannot move to shows greyed out with the reason underneath, as described on [Project Lifecycle](/handbook/workspace/project-lifecycle).

## The project page

The **Overview** shows the details, the procurement and production figures such as **Total ordered** and **Total delivered**, and links to the other tabs. **Bill of Material** lists the bought items, made items and source items with their demand status. **Orders** lists the supplier orders with the cost for the project, and **Costs** splits it by supplier. **Calculations** and **Checklists** appear while those features are switched on and hold the project's documents, with **New Calculation** and **New Checklist**; see [Revisions and Release](/handbook/workspace/document-revisions).

## Deleting a project

**Delete** needs **Manage Projects** and a project without open work: no open lots, production orders, order lines, demands or quote requests. Otherwise the button shows disabled, and its tooltip names what is missing or counts the open work.

## Examples

**A new customer order.** You create project 24-118 for product M-2045, set the bought item date to 3 March and add the demands. Each new bought item demand starts with 3 March.

**A delivery date moves.** The customer pushes the machine back two weeks. You change **Required Delivery Date (Made Items)** and pick **Apply to all**, and every open made item demand of the project moves along.

**A project created by mistake.** It has no demands yet, so someone with **Manage Projects** deletes it from the list.
