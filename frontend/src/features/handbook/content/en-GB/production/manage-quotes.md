---
title: Manage Quotes
summary: How to put lot positions a supplier could work on a quote request, from the lots table or the lot page, and what the award does with them.
sourceRefs:
  - frontend/src/features/production/lots/components/LotsListManageQuotesPanel.vue
  - frontend/src/features/production/lots/components/LotManageQuotesPanel.vue
  - frontend/src/features/quote-requests/components/QuoteRequestPanel.vue
  - backend/src/modules/fulfillment/application/use_cases/quote_request/_lines.py
  - backend/src/modules/fulfillment/application/use_cases/quote_request/award_quote_request.py
lastVerified: 2026-11-10
---

When a step such as coating or hardening goes to a supplier, you may want prices from several suppliers before you order. **Manage Quotes** puts lot positions on a quote request instead of an order. The suppliers quote on the request, and its award later puts each position on the order of the supplier that won it, as [Manage Orders](/handbook/production/manage-orders) would. How a quote request is sent, compared and awarded is explained in [Quotes](/handbook/procurement/quotes).

## From the lots table {#list}

Click **Manage Quotes** on the Lots tab. It needs **Write Production Lots** and **Write Orders**, and shows disabled with a tooltip naming the one you lack. Click steps in the table to add their positions to the panel. Each row names the lot and the position, the part number and the methods, and starts with the quantity the position still has to give. You can lower it, but not raise it above that.

Pick a draft or sent request under **Quote request**, or create one with **New Quote Request**, and click **Add to Quote Request**. The lines are added and the selection is cleared. **Clear Selection** empties the panel without adding anything.

## From the lot page {#lot}

On the lot page, click **Manage** and then **Manage Quotes** above the positions. It needs **Write Orders**. The panel lists every position of the lot that a supplier may still work, with its open quantity. Remove a row you do not want to ask for with **Leave Out**, then add the rest as above.

## What happens next {#award}

A position on an open request shows **In Quotation** in the lots table and on the lot page. The request reserves nothing, so the position can still be ordered through Manage Orders in the meantime. When the request is awarded, each position goes on a draft or partially ordered order of its winning supplier, with the quoted quantity or what the position still has to give, whichever is smaller. A position that can no longer be assigned, because it is already on a live order line, its lot has ended or nothing remains, keeps its request line open with a warning.

## Examples

Position 3 of a lot of 40 pieces needs powder coating. Open the lot page, click **Manage** and **Manage Quotes**, leave out every other position, pick the request for this month's coating and click **Add to Quote Request**.

Five lots need anodizing. On the Lots tab, open **Manage Quotes**, click the anodizing step of each lot, create a new request with **New Quote Request** and add all five lines to it at once.

A position was ordered through Manage Orders before the request was awarded. The award skips it, and its request line stays open with a warning, so you can drop it from the request.
