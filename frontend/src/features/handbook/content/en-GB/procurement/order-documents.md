---
title: Order Mails, Dockets and Files
summary: How to send the request and order mails, what the status question after a mail does, and how dockets, extra costs and order files work.
sourceRefs:
  - frontend/src/features/orders/composables/useOrderMailComposer.ts
  - backend/src/modules/fulfillment/application/use_cases/order/mark_order_item_ordered.py
  - backend/src/modules/fulfillment/application/use_cases/order/set_order_extra_costs.py
  - backend/src/modules/fulfillment/domain/services/extra_cost_rules.py
  - backend/src/modules/fulfillment/application/use_cases/order/upload_order_file.py
  - backend/src/modules/fulfillment/application/use_cases/order/_file_kind.py
  - backend/src/modules/quality/application/use_cases/print_document/print_document.py
lastVerified: 2026-11-10
---

An order collects what goes to the supplier and what comes back: the mails you send, the docket that travels with the goods, the extra costs on the invoice and the files such as the order confirmation. All of them are reached from the order page, and the mails and dockets also from a right-click on the order in the Orders list.

## Request Mail and Order Mail {#mails}

**Request Mail** asks the supplier about the order, and **Order Mail** places it. Each opens **Compose Mail** with the address, subject and text already filled in from the supplier's settings, with the lines in a table. The request mail uses the supplier's request address, template and language where they are set, and falls back to the order ones otherwise, see [Suppliers](/handbook/resources/suppliers). A supplier without a template uses the default from the settings, and when neither exists, the app says that no template is configured. Check the text, change it if needed and choose **Send**. Sending needs **Send Mail**, and without it both buttons show disabled with a tooltip.

## After the mail is sent {#post-send}

Once a request or order mail has gone out, the dialog **Mail Sent, Update Status?** asks whether to record it on the lines. **Mark All as Requested** marks every pending line requested, and **Mark All as Ordered** marks every pending and requested line ordered, which is the usual choice after an order mail. The button that fits the mail you sent is highlighted. **Skip** changes nothing. You can mark the lines later from the order page, see [Order Line Actions](/handbook/procurement/order-line-actions#request-order). After a cancellation mail the dialog does not ask, since the order is already canceled.

## Dockets {#dockets}

Right-click the order in the Orders list and choose **Print Docket** to send the order docket to its printer, or **Download Docket** to save it as a PDF. Both need **Print Documents**. How the docket looks is set up under [Print Dockets](/handbook/resources/print-dockets).

## Extra costs {#extra-costs}

**Extra Costs** on the order page opens a list of costs beyond the lines, such as shipping, packaging, surcharges or a discount. **Add Cost** adds a row with a **Kind**, an **Amount** and an optional **Label** and **Note**, and **Line** ties the cost to one line. Left empty, it shows **Whole order** and the cost belongs to the whole order. The amount must be above zero, a **Discount** is subtracted, and the kind **Other** needs a label. The costs stay editable after delivery, since shipping is often known only from the invoice, but a canceled order takes none. They need **Write Orders** while the order is a draft or requested and **Manage Orders** after that. An award from a quote request brings the offer's costs along.

## Order files {#files}

When file storage is set up, **Add File** stores a PDF as **Proposal**, **Order Confirmation**, **Delivery Note**, **Invoice** or **General**, or an image under **Pictures**, and **Take Picture** uses the camera. Each file may be up to 25 MB. The files show in the panel beside the lines, and deleting one asks first. Adding and deleting files needs **Write Orders**.

## Examples

**Placing an order.** On a draft order, choose **Order Mail**, check the lines and send. In the next dialog choose **Mark All as Ordered**, and the order reads ordered.

**Shipping on the invoice.** The invoice of a delivered order adds 18.50 for shipping. Open **Extra Costs**, add a **Shipping** row with 18.50 on the whole order and save, and the order's total includes it.

**A photo of the delivery note.** At goods receipt, open the order on a tablet, choose **Add File** and **Take Picture**, and photograph the delivery note. The picture is stored with the order under **Pictures**.
