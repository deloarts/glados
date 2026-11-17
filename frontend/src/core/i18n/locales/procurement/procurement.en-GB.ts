// Messages for procurement, merged into the en-GB locale.
export default {
  sections: {
    orders: 'Orders',
    quotes: 'Quotes',
    boughtItemsDemand: 'Bought Items Demand',
    madeItemsDemand: 'Made Items Demand',
    sourceItemsDemand: 'Source Items Demand',
  },
  timeline: {
    empty: 'No orders with dates to show yet.',
    columns: {
      orderNumber: 'Order Number',
      status: 'Status',
      orderDate: 'Order Date',
      durationDays: 'Duration (days)',
    },
  },
  unitMismatchSummary:
    'An order line this demand draws on is in another unit. Its pieces count one to one, nothing is converted.',
  unitMismatch:
    'The demand is in {demand}, the order line in {line}. Its pieces count one to one, nothing is converted.',
}
