---
title: Orders
summary: What the Orders list, the timeline and the order page show, how to find an order, and where each order action is explained.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/order/create_order.py
  - backend/src/modules/fulfillment/application/use_cases/order/get_order.py
  - backend/src/modules/fulfillment/application/use_cases/order/update_order.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
lastVerified: 2026-11-12
---

Under **Procurement**, the **Orders** tab lists every supplier order. An order groups the lines you buy from one supplier, or the steps of a lot you send to one. Most orders start from a demand list or a quote request award, and **New Order** starts an empty one with a **Supplier** and an optional **Note**. Creating an order needs **Write Orders**.

## The list {#list}

Each row shows the **Order #**, the **Status**, the **Supplier**, the number of **Items**, the **Total (net)**, the **Ordered**, **Exp. Delivery** and **Delivered** dates, the **Storage** place and the **Note**. Click a row to expand it into its lines, and click the order number to open the order page. Right-click a row for the order's actions. **Export** saves the filtered orders as an Excel file, see [Exporting Demands and Orders](/handbook/procurement/list-export).

The bar above the table searches by order number, supplier and the items on the lines, such as an order code or a lot number. It sorts by order number, ordered date or expected delivery, and groups by **Status** or **Supplier**. **Hide Delivered** and **Hide Canceled** keep the list to the open orders. When file storage is set up, **Missing Invoice** keeps only the orders without an invoice file, and **Show Files** adds a column with each order's files.

## The timeline {#timeline}

**Timeline** draws the orders as bars from the ordered date to the delivery date, or to the expected delivery while nothing has arrived. It shows every open order and those delivered or canceled in the last 30 days, and **Hide Delivered** and **Hide Canceled** apply here too. A line with dates of its own appears as a bar below its order. **Back to List** returns to the table.

## The order page {#page}

The bar at the top shows the status, the expected or actual delivery date, the storage place and the quote requests the lines came from. A delivered order without an invoice file shows **Invoice missing**. The buttons below add lines and files, edit the extra costs, change the **Supplier**, the **Expected Delivery Date**, the **Storage Place** and the **Note**, mark all lines, send mails and cancel the order. **Add Item** adds a **Bought item** or a **Virtual line** for something that is not in the catalogue. The note and the files sit in a panel beside the lines, which **Hide Files Panel** folds away. On a phone the page shows only the lines with their item, quantity and status.

Who may change what in which status is explained in [Order Lifecycle](/handbook/procurement/order-lifecycle#permissions). An action your permissions do not allow shows disabled, and where the app knows the missing permission, its tooltip names it.

## Where each action is explained

The statuses are in [Order Lifecycle](/handbook/procurement/order-lifecycle), and requesting, ordering, moving, closing short and canceling are in [Order Line Actions](/handbook/procurement/order-line-actions). Goods receipt is in [Marking an Order Line as Delivered](/handbook/procurement/order-item-delivery), and mails, dockets, extra costs and files are in [Order Mails, Dockets and Files](/handbook/procurement/order-documents). Asking several suppliers for prices first is described in [Quote Requests](/handbook/procurement/quotes).

## Examples

**What is late?** Turn on **Hide Delivered** and **Hide Canceled** and sort by expected delivery, earliest first. The orders at the top are the ones to chase.

**Invoices to collect.** Turn on **Missing Invoice** and **Hide Canceled**. The list shows every order without an invoice file, and the delivered ones among them are the invoices to ask the suppliers for.

**Where is this part?** Type the order code of a bought item into the search. The list shows every order with a line for it, and expanding a row shows the line with its status.
