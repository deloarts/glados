---
title: Order Lifecycle
summary: How the status of a supplier order and of each of its lines follows from what was requested, ordered, delivered and canceled, and who may change a line in which status.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/order.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/order_item.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/domain/services/order_rules.py
  - backend/src/modules/fulfillment/application/use_cases/order/update_order.py
  - backend/src/modules/fulfillment/application/use_cases/order/update_order_item.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

A supplier order and each of its lines show a status that the app works out from what you recorded: what was requested, ordered, delivered and canceled. You never set it directly. You request, order, deliver, close short or cancel, and the status follows. What each of these actions does is described in [Order Line Actions](/handbook/procurement/order-line-actions).

<StateMachineEmbed machine-key="order_status" />

## How the order's status is worked out

A canceled order is **Canceled**, and so is an order whose lines are all canceled. Apart from that, canceled lines do not count: an order with one canceled line and one delivered line is **Delivered**. Once anything has arrived on a line that is not canceled, the order is **Partial** until every such line is delivered.

An order whose lines were all marked as ordered is **Ordered**, and it stays ordered when you add a line later. An order with some lines ordered and others still pending or requested is **Partly Ordered**. It counts as submitted, so canceling it needs **Manage Orders**, but you can still add lines to it, also from a [quote request award](/handbook/procurement/quotes#award), and order its remaining lines. A correction that takes every delivered piece back leaves it partly ordered rather than draft. **Requested** and **Draft** come before that.

## The lines

<StateMachineEmbed machine-key="order_item_status" />

A line starts **Pending**, becomes **Requested** and **Ordered**, and then **Partial** and **Delivered** as goods arrive, see [Marking an Order Line as Delivered](/handbook/procurement/order-item-delivery). Delivered counts the accepted pieces plus the pieces written off as lost. Pieces accepted by mistake are taken back with a [correction](/handbook/procurement/delivery-correction).

## Who may change what {#permissions}

Creating an order and changing a draft or requested one needs **Write Orders**. Once the supplier holds something, changes need **Manage Orders** as well: that applies to an ordered or delivered line, and to every line once the order is ordered or delivered. On a partly ordered order, the pending and requested lines stay open to everyone with **Write Orders**, so the buyer can finish ordering it. An action your permissions do not allow shows disabled, and its tooltip names the missing permission.

A canceled line takes no more edits, and an order someone canceled keeps its header and takes no new line. On a line that has received goods, the item, unit and project stay as they arrived. Changing the order's supplier moves along the lines that named the old supplier. Once a line is ordered, it is already with that supplier, so the supplier can no longer change. Setting an expected delivery date for all lines reaches only the lines still waiting for goods.

## Examples

**One line canceled.** An order has two lines. Line A arrives in full, line B is canceled because the item is no longer needed. The order is delivered.

**Supplier ships less.** Ordered 10, 8 arrive, and the supplier says the last 2 will not come. **Close Short** on the line delivers it at 8, and the demand it covered shows 2 pieces missing, see [Closing a line short](/handbook/procurement/order-line-actions#close-short).

**Finishing a partly ordered order.** You mark line A as ordered by phone, while line B is still pending. The order reads partly ordered. A colleague with **Write Orders** only can still mark line B as ordered, and the order then reads ordered.
