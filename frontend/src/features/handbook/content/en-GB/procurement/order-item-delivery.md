---
title: Marking an Order Line as Delivered
summary: What the delivered and rejected quantities, the storage place and the material references mean when you book a supplier delivery, and how a rejected piece continues.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/order/process_order_item_delivery.py
  - backend/src/modules/fulfillment/application/use_cases/order/deliver_all_order_items.py
  - backend/src/modules/fulfillment/application/use_cases/order/_made_line_delivery.py
  - backend/src/modules/fulfillment/domain/services/delivery_booking_rules.py
  - backend/src/modules/fulfillment/domain/value_objects/material_receipt.py
  - backend/src/modules/fulfillment/domain/services/order_rules.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
lastVerified: 2026-11-13
---

The **Mark as Delivered** dialog books one goods receipt for one order line. A line that arrives in several shipments is booked once per shipment. The line counts as delivered once the accepted pieces, plus any pieces written off as lost, reach the ordered quantity. Booking needs **Receive Deliveries**, and without it the action stays disabled.

Only an ordered or partially delivered line of an order that is not canceled takes a delivery, and a line for a lot only while the lot is not canceled. **Mark All as Delivered** books all such lines together, or none if one fails, also on a partly ordered order. It tells you how many lines it left out.

## The two quantity fields

**Quantity Delivered** is the number of pieces you accept into stock with this booking. It is preset to the remaining quantity of the line, so for a complete, undamaged shipment you only confirm. If the supplier sent fewer pieces than ordered, lower the number, and the line stays partially delivered and waits for the rest.

**Quantity Rejected** sits in the **Reject pieces** block and stays at zero unless you open it. It counts the pieces you do not accept because they are damaged, wrong or out of specification.

The two numbers together may not exceed what is still open on the line, unless the line's over-delivery tolerance allows more, see [Delivery Tolerances](/handbook/procurement/delivery-tolerances). On a line for a lot, the accepted pieces must also fit what the previous step of the lot made available.

## Storage place and material references {#material}

**Storage Place** is optional. It says where the goods went, such as a shelf. Left empty, the booking keeps the line's earlier storage place.

The block **Batch, delivery note and certificate** is optional too and holds **Batch or Heat Number**, **Delivery Note** and **Certificate (EN 10204 3.1)**, each up to 100 characters. They stay with the delivery, so raw material can be traced to the lot that uses it. **Mark All as Delivered** asks for one **Delivery Note** and records it on every line it books.

## Damage noted on the delivery note {#damage-noted}

Tick **Damage noted on the delivery note** when you wrote the damage onto the carrier's delivery note while signing for the goods, such as a crushed box or a torn pallet wrap. A claim against the carrier usually depends on that note, so the delivery history marks the booking with a truck icon. The tick does not reject anything by itself: book damaged pieces as rejected below, and if the damage only shows once the box is open, reject them afterwards, see [Correcting a Delivery](/handbook/procurement/delivery-correction#damage). **Mark All as Delivered** has the same tick for the whole shipment.

## Reason and outcome

Every rejected piece needs a **Reason** and an **Outcome**.

**Supplier re-delivers** means the piece is still owed. The line keeps its ordered quantity and stays partially delivered. The expected delivery date is cleared until you enter the date the supplier confirms.

**Piece is lost** means the piece will not come back. It counts toward closing the line, so the line can reach delivered without it. On a bought or raw material line, the demands allocated to it shrink to what the line can still bring, and the missing piece shows up on the newest demand again. For a part of a lot, the lot is closed short by that quantity, the loss appears as scrapped on the lot, and a replacement lot is created unless you untick **Create replacement lot**.

## Examples

**Complete shipment.** Ordered 10, all 10 arrive intact. Confirm the preset 10 and save. The line is delivered.

**Short shipment.** Ordered 10, only 8 arrive. Set **Quantity Delivered** to 8 and save. The line shows 8 of 10 and remains open. When the last 2 arrive, the dialog is preset to 2.

**One damaged piece, supplier sends a new one.** Ordered 10, 10 arrive, one is dented. Enter 9 delivered and 1 rejected, with the reason **Supplier Damage** and **Supplier re-delivers**. The line shows 9 delivered and 1 still open.

Rejections stay in the line's **Delivery History** and feed the **Rejected at Receipt by Supplier** panel on the KPI page. Photos of the damage go onto the booking in the **Pictures** column of the delivery history. To take back pieces accepted by mistake, or to reject pieces whose damage you find later, see [Correcting a Delivery](/handbook/procurement/delivery-correction).
