---
title: Order Line Actions
summary: How to request, order, move, remove, close short and cancel order lines, how to cancel a whole order, and when each action is offered.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/application/use_cases/order/mark_order_item_ordered.py
  - backend/src/modules/fulfillment/application/use_cases/order/mark_order_item_ready_for_pickup.py
  - backend/src/modules/fulfillment/application/use_cases/order/move_order_item.py
  - backend/src/modules/fulfillment/application/use_cases/order/delete_order_item.py
  - backend/src/modules/fulfillment/application/use_cases/order/close_order_item_short.py
  - backend/src/modules/fulfillment/application/use_cases/order/reopen_order_item.py
  - backend/src/modules/fulfillment/application/use_cases/order/cancel_order_item.py
lastVerified: 2026-11-10
---

Right-click a line on the order page, or in the expanded row of the Orders list, to see what you can do with it. The menu greys out the actions the line's status does not allow. An action your permissions do not allow is greyed out too, and its tooltip names the missing permission, see [Order Lifecycle](/handbook/procurement/order-lifecycle#permissions).

## Requesting, ordering and pickup {#request-order}

**Mark as Requested** records that you asked the supplier about a pending line. **Mark as Ordered** records that you ordered a pending or requested line. On the order page, **Mark All as Requested** and **Mark All as Ordered** do the same for every line that can take it. After a [request or order mail](/handbook/procurement/order-documents#mails) the app offers the same choice.

**Mark Ready for Pickup** applies to an ordered or partially delivered line that has an **Exp. Pickup** date and was not marked yet. It records that the goods are ready now, and the line shows a check mark with the time. A line for a lot then plans the next steps of the lot from that moment.

## Moving and removing a line {#move}

**Move to Another Order** takes a pending, requested or ordered line on which nothing was delivered or rejected to another open order. Choose the **Target Order**. When that order has another supplier, the line takes it over. A line that is already ordered is still with the old supplier, so the dialog warns you and moves it only once you tick the box saying that you settle the order with that supplier yourself. Moving needs **Write Orders** while both orders are draft or requested, and **Manage Orders** as well once the line or one of the orders is past requested, see [Who may change what](/handbook/procurement/order-lifecycle#permissions).

**Remove Item** deletes a pending or requested line, and its demands go back to open. An ordered line is canceled instead.

## Closing a line short {#close-short}

When the supplier will not send the rest, use **Close Short** on an ordered or partially delivered line that has received something. The line's quantity drops to what arrived, so the line is delivered, and its demands shrink to the accepted pieces, starting with the newest demand, so the missing part shows up on them again.

If the supplier sends the rest after all, or a delivery needs a [correction](/handbook/procurement/delivery-correction), use **Reopen Line**. The quantity goes back to what it was, and the line waits for the rest again. A line of a canceled order and a line for a lot are not reopened. A lot line closed short leaves the missing pieces open on its lot position, which offers **Assign Externally** or **Assign Internally** again for the rest.

## Canceling a line {#cancel-line}

**Cancel Line** cancels a pending, requested or ordered line that has received nothing. Its demands lose the allocation and show that part of their need as open again.

## Canceling an order {#cancel}

**Cancel Order** works until the order is delivered, and past requested it needs **Manage Orders**. Delivered lines stay as they are, partially delivered lines are closed short at what arrived, and the other lines are canceled and give their demands back. With **Send Mail**, the app then asks **Notify Supplier?** and composes the cancellation mail.

## Examples

**Canceling a half delivered order.** Line A has 10 of 10, line B 4 of 10, line C nothing. **Cancel Order** leaves A delivered, closes B short at 4 and cancels C, whose demands are open again.

**A line on the wrong order.** You booked 20 screws on the order of supplier A and already ordered them, but supplier B should deliver them. Move the line to the draft order of supplier B, tick the confirmation and call supplier A to cancel the screws there.

