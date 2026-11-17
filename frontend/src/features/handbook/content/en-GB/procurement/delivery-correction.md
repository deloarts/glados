---
title: Correcting a Delivery
summary: How to take back pieces you booked as accepted by mistake or reject pieces whose damage you found later, what a correction does to the line and its order, and how it shows on the KPI page.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/order/correct_order_item_delivery.py
  - backend/src/modules/fulfillment/domain/services/order_rules.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/application/use_cases/order/_lines.py
  - backend/src/modules/fulfillment/domain/services/delivery_booking_rules.py
  - backend/src/modules/fulfillment/application/use_cases/order/upload_delivery_picture.py
lastVerified: 2026-11-13
---

A delivery booking is never edited or deleted. When you accepted too many pieces, for example because a box was counted twice, you book a correction instead: a new record in the delivery history that takes the pieces back. The history then shows both the original booking and the correction, and the line's delivered quantity is the sum of the two.

## Booking a correction

Open the **Delivery History** of the line and use **Correct Delivery**, the undo button in the **Correction** column, on the booking that was wrong. Enter the **Pieces to take back** and a **Reason**, then **Book Correction**. The reason is required, so whoever reads the history later knows why the pieces disappeared.

You can take back at most what that booking accepted, less what earlier corrections of the same booking already took back. Only accepted pieces are corrected, and rejected and lost pieces stay as they were booked. You need **Receive Deliveries**. Without it the button shows disabled, and its tooltip names the missing permission.

## Damage found after receipt {#damage}

Hidden damage often shows only when the goods are unpacked or inspected, after they were booked as accepted. Use **Report Damage**, the button beside the undo button, or choose **Damage found after receipt** under **What happened?** in the correction dialog. Instead of a reason you pick the rejection **Reason**, such as **Transport Damage**, and the **Outcome**, as at receipt, and you may add a **Note** and pictures. **Reject Pieces** takes the pieces back as rejected ones.

**Supplier re-delivers** reopens the line, and its expected delivery date is cleared until the supplier confirms a new one. **Piece is lost** leaves the line delivered, because the supplier sends nothing for the piece, and the demands allocated to the line shrink to what it still delivered, so the missing piece shows up on a demand again and can be ordered anew. Either way the rejection is announced to everyone who can edit orders, and it counts on the KPI page like a rejection at receipt. The same limits apply as to a correction.

## Pictures {#pictures}

The **Pictures** column of the delivery history holds photos of a booking, such as the damage or the stamped delivery note. **Add Picture** takes JPEG, PNG or WebP files, and on a phone it offers the camera. A picture also shows among the order's own files. Adding and removing a picture needs **Receive Deliveries**.

## When a line cannot be corrected

A line that belongs to a lot cannot be corrected here, because its lot already counts the delivered pieces as done. A line of a canceled order is refused, because nothing can deliver it any more and it would stay open for good. A line that was closed short is refused until you reopen it, see [Order Line Actions](/handbook/procurement/order-line-actions#close-short).

A demand that the line's deliveries fulfilled does not stop a correction: it goes back to ordered or allocated and shows the missing pieces again. A correction is refused only while a demand allocated to the line has used up the pieces, that is a demand someone marked fulfilled by hand, or a raw material demand whose lot already processed pieces at its first step.

## What a correction does to the line

A correction can reopen a line. A delivered line becomes partially delivered again and waits for the rest. The order follows its lines, so a delivered order can become partial again.

A line may have taken more than its quantity within its [over-delivery tolerance](/handbook/procurement/delivery-tolerances#over), and the extra pieces may have gone to other demands. A correction that takes those pieces back fits the line's allocations to what the line still delivered, so a demand that relied on the extra pieces shows them as missing again.

## On the KPI page

The KPI page counts a correction on its own date, not on the date of the booking it corrects. A period that holds only the correction therefore shows a negative delivered amount for that supplier.

## Examples

**Dented after unpacking.** Ordered 10, booked 10, and two turn out dented when the box is opened. Use **Report Damage** on the booking, take back 2 with **Transport Damage** and **Supplier re-delivers**, and add a photo. The line shows 8 of 10 and waits for the replacements.

**Counted twice.** Ordered 10, booked 10, but only 9 are in the box. Correct the booking by 1 with the reason "counted twice". The line shows 9 of 10 and waits for the last piece.

**After closing short.** The supplier sent 8 of 10 and you closed the line short at 8. Later two of the 8 turn out to belong to another order. Reopen the line, which brings back its quantity of 10, and correct the booking by 2: the line shows 6 of 10 and waits for the rest. If the supplier sends nothing more, close it short again at 6.

**A fulfilled demand.** The 10 pieces of a line fulfilled a project's demand, and one of them was counted twice. Correct the booking by 1: the demand is no longer fulfilled and shows the missing piece. Had someone marked the demand fulfilled by hand, the correction would be refused, because the project may already have used the pieces.
