---
title: Allocating Demands
summary: How a bought or raw material demand is covered by order lines and stock through Auto-Allocate, Manage Allocations and Fulfill from Stock, and how a substitute item is recorded.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/_demand_family/auto_allocate.py
  - backend/src/modules/fulfillment/application/use_cases/_demand_family/allocation_writers.py
  - backend/src/modules/fulfillment/application/use_cases/_demand_family/fulfill_from_stock.py
  - backend/src/modules/fulfillment/domain/services/allocation_coverage.py
  - backend/src/modules/fulfillment/domain/services/allocation_service.py
  - frontend/src/features/procurement/components/BoughtItemManageAllocationsDialog.vue
  - frontend/src/features/production/source-item-demands/components/SourceItemManageAllocationsDialog.vue
lastVerified: 2026-11-10
---

An allocation ties part of a demand to what covers it: a quantity on an order line, or a quantity taken from stock. Bought item demands and raw material demands are allocated this way, and their status follows from it, see [Bought Item Demand Lifecycle](/handbook/procurement/bought-item-demand-lifecycle). Made item demands are covered by lots instead and use only the stock part. Every action here needs **Write Allocations**; without it the action shows disabled and the tooltip names the missing permission. A fulfilled or canceled demand takes no new allocation.

## Auto-Allocate

**Auto-Allocate** in the row menu or in the demand dialog looks for order lines of the demand's own item whose status is **Ordered** or **Partial** and fills the demand from them. It prefers ordered lines over partly delivered ones, then the earliest expected delivery, then the line with the most left, so it touches as few lines as possible. A line shared with other demands only offers what they do not hold yet. Lines that are still **Pending** or **Requested** are never used, and when nothing fits a message says "No matching order items found."

## Manage Allocations

**Manage Allocations** in the row menu, or **Manage** in the demand dialog, opens a list of every allocation of the demand. Change a quantity and save it with the check mark, or remove the allocation with the bin. Under **Link Order Item** you search an order by its number or supplier, in any status, then choose the line and the quantity and press **Add**. A manual link works for a line in any status, so you can tie a demand to a line that is still being requested; the demand then stays Allocated until the line is ordered. For a raw material demand, **Create new order item for this material** adds a line to the chosen order and links it in one step with **Create & Allocate**. **Add Stock Allocation** records the part that comes from the shelf; a demand has one stock allocation, which you change in its row.

Glados refuses an allocation that is larger than what the demand still lacks or than what the line has free, a canceled line, and one that would take pieces already delivered for another demand. A line in another unit is allowed with a warning, because nothing is converted.

## Fulfill from Stock

**Fulfill from Stock** covers part of a demand straight from the shelf, at most what is not yet allocated. Use it in the row menu, in the demand dialog, or for several selected demands at once in the **Manage Stock** panel. Glados only records how much was taken; it does not keep the stock level itself.

## Substitutes

Linking a line of a different bought item records a substitution: the dialog warns "Different item than the demand, will be linked as a substitution." and asks for an optional reason. A raw material demand may take any source item line of the order as a substitute, while a bought item material must match exactly. The demand dialog lists substitutes under **Ordered as substitute**, and the row shows "Fulfilled with a substitute item".

## Examples

**The normal case.** A demand for 20 cable glands, and an ordered line for 50 has 30 free. **Auto-Allocate** takes 20, and the demand reads Ordered.

**A line still being requested.** **Auto-Allocate** finds nothing, so you link the line in **Manage Allocations**, and the demand waits as Allocated.

**Part from the shelf.** Four of ten fuses are in stock. **Fulfill from Stock** with 4 covers them, and the other six are ordered.
