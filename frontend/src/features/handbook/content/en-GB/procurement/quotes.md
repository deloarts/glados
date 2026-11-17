---
title: Quote Requests
summary: How to ask several suppliers for prices, compare their offers, award the lines onto orders, and what closing, canceling, substitutes and voided awards do.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/quote_request.py
  - backend/src/modules/fulfillment/application/use_cases/quote_request/edit_quote_request.py
  - backend/src/modules/fulfillment/application/use_cases/quote_request/award_quote_request.py
  - backend/src/modules/fulfillment/application/use_cases/quote_request/_lines.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

A quote request asks several suppliers for prices on the same lines, so you can order from the cheapest. The **Quotes** tab under **Procurement** lists the open requests, and **Show Closed** adds the ones that ended. Most requests start from **Manage Quotes** on a demand list, and **New Quote Request** starts one with the **Suppliers to ask**, an **Offers due** date and a **Note**. Nothing on a request changes an order or a demand until you award it. Every change needs **Write Orders**, and a disabled button names the missing permission or the reason in its tooltip.

<StateMachineEmbed machine-key="quote_request_status" />

Every status change with its cause is listed in [Quote Request Transitions](/handbook/procurement/quote-request-transitions).

## Asking the suppliers {#send}

**Add Suppliers** adds more suppliers to ask. For each supplier, **Send Request** composes the request mail, which also needs **Send Mail**, and **Mark Sent** records a request you sent another way. Once one supplier was asked, the request reads **Sent**. A line added afterwards shows **Not asked yet** for the suppliers who already have the request.

## Entering offers {#offers}

**Enter Offer** records what a supplier quoted: a **Unit price**, **Lead time in days** and **Minimum quantity** per line, or **No offer** for a line it skips. **Offer Alternative** records another item the supplier offers instead. **Extra Costs**, **Documents**, **Valid until** and **Note** cover the whole offer, and **The supplier declined to quote** marks a refusal. The table marks the cheapest price per line and the **Cheapest overall** offer.

## Awarding {#award}

Click an offer cell to choose that supplier for a line, or use **Choose Cheapest**. **Award Selected** awards the chosen lines, and **Award All To** gives every open line to one supplier. The **Award Lines** dialog names an **Order** per winning supplier, either a **New draft order** or one of its draft or partly ordered orders, and the **Extra costs on the order**, filled in from the offer. Each line goes onto that order with the demands it was asked for, cut to what each demand still needs.

## Closing, canceling and dropping {#close}

**Drop** takes a line out of the award, and **Take Back** returns it. **Remove** deletes a line with its offers. **Close** ends a request with an awarded line and drops the lines still open, while **Cancel Request** ends a request that awarded nothing, and its demands stay open.

**Substitute** replaces a bought or source item line with another item of the same kind for every supplier. The old line is dropped and the new one takes over its quantity and demands. Send the request again to the suppliers already asked. Removing the new line brings the old one back.

## Voided awards and Reopen {#reopen}

Canceling or removing an order line that came from an award gives the award back. The request line opens again, shows **Voided**, and can be awarded anew. A request someone closed stays closed and only notes the voided award, so **Reopen** clears the close. The offers stay, and the request reads sent or draft again.

## Examples

**Three suppliers asked.** You send the request to three suppliers and enter their offers. **Choose Cheapest** picks a supplier per line, and **Award Selected** puts the lines on two new draft orders.

**An alternative item.** A supplier offers a similar bearing instead. You record it with **Offer Alternative**, and if it wins, the order line carries the alternative item.

**A voided award.** After closing the request, the supplier cannot deliver and you cancel the order line. **Reopen** the request and award the line to the second cheapest supplier.
