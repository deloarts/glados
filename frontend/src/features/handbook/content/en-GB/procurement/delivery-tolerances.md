---
title: Delivery Tolerances
summary: How far a supplier delivery may go over or under the ordered quantity, where the tolerances are set and what happens to the line in each case.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/delivery_tolerance.py
  - backend/src/modules/fulfillment/application/services/delivery_tolerances.py
  - backend/src/modules/fulfillment/application/use_cases/order/process_order_item_delivery.py
  - backend/src/modules/fulfillment/domain/services/delivery_booking_rules.py
lastVerified: 2026-11-10
---

Suppliers rarely ship exactly what was ordered, so a line may be delivered a little over or under its quantity. The tolerances say how far, in percent of the line's ordered quantity. Both start at 0, which takes exactly the ordered quantity and keeps a line open until it is delivered in full.

## Where the tolerances are set {#settings}

The global pair sits under **Settings**, on the **Production** tab of **System Settings**, in the **Deliveries** section, as **Over-Delivery Tolerance** and **Under-Delivery Tolerance**. Changing them needs **Write Settings**.

A bought item or a source item can carry a pair of its own in its edit form, under the same two names. A field left empty shows **As in the settings** and takes the global value, and a value entered there replaces the global one for that item only. A virtual line has no catalogue item and always takes the global values. A line for a made part sent to a supplier has no tolerance, since it carries the counted pieces of its lot.

## Over-delivery {#over}

Within the over-delivery tolerance you can book more than the line still awaits, and the delivery dialog tells you by how much. The extra pieces are delivered on the line and are free to allocate to another demand. A booking beyond the tolerance is refused, and the message names how much more the line takes. In pieces, sets and other counted units the allowance is rounded down to whole pieces, so a tolerance never admits a fraction of a piece.

## Under-delivery {#under}

The booking that brings the line within the under-delivery tolerance of its quantity closes it short, exactly as **Close Short** does. The line's quantity becomes what it received, its allocations are fitted to what arrived, and the missing pieces stay open on the demand, where you can order them again or take them from stock. A booking that sends pieces back for redelivery keeps the line open, since more is coming. A line closed short this way can be reopened with **Reopen Line**, see [Order Line Actions](/handbook/procurement/order-line-actions#close-short).

## Examples

**Over-delivery within the tolerance.** Ordered 100, tolerance 5 %, the supplier sends 103. Book 103, and the dialog notes 3 more than the line awaits. The line is delivered with 103, and the 3 extra pieces can be allocated to another demand.

**Under-delivery within the tolerance.** Ordered 100, tolerance 2 %, the supplier sends 98 and nothing more. Book 98. The line closes short at 98, and the 2 missing pieces stay open on its demand.

**Too much for the tolerance.** Ordered 10 pieces, tolerance 5 %. The allowance is half a piece, which rounds down to nothing, so a booking of 11 is refused. Book 10 and send the extra piece back, or raise the item's own tolerance first.

**An item with its own tolerance.** Cable is ordered in metres and the supplier always cuts a little long. You set the cable's **Over-Delivery Tolerance** to 10 while the settings keep 0. Its lines take up to 10 % more, and every other item still takes exactly what was ordered.
