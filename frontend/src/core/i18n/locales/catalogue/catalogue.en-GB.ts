// Messages for catalogue, merged into the en-GB locale.
export default {
  itemDetail: {
    notFound: 'This item does not exist or has been deleted.',
    loadError: 'The item could not be loaded.',
    sectionError: 'Could not load this section.',
    truncated: 'Showing the first {limit} entries only.',
    actions: {
      edit: 'Edit item',
      createDemand: 'Create demand',
      addToOrder: 'Add to order',
      print: 'Print',
      printLabel: 'Label',
      printDocket: 'Docket',
    },
    media: {
      openFile: 'Open {name}',
      placeholderName: '3D preview',
    },
    print: {
      labelSent: 'Label sent to printer.',
      labelFailed: 'Could not print the label.',
      docketSent: 'Docket sent to printer.',
      docketFailed: 'Could not print the docket.',
    },
    cards: {
      item: 'Item',
      files: 'Files',
      demands: 'Demands',
      orders: 'Orders',
      lots: 'Lots',
      usedIn: 'Used in',
      changelog: 'Changelog',
      processes: 'Processes',
    },
    demands: {
      empty: 'No demands for this item.',
      columns: {
        id: 'Demand',
        status: 'Status',
        quantity: 'Quantity',
        project: 'Project',
        desiredDelivery: 'Desired delivery',
        created: 'Created',
        alteration: 'Alteration',
        lot: 'Lot',
      },
    },
    orders: {
      empty: 'This item has not been ordered yet.',
      columns: {
        orderNumber: 'Order',
        supplier: 'Supplier',
        orderStatus: 'Order status',
        quantity: 'Quantity',
        itemStatus: 'Position status',
        project: 'Project',
        orderedDate: 'Ordered',
        deliveryDate: 'Delivered',
        price: 'Price',
      },
    },
    lots: {
      empty: 'No lots for this item.',
      columns: {
        lotNumber: 'Lot',
        status: 'Status',
        quantity: 'Completed / quantity',
        project: 'Project',
        requiredDelivery: 'Required delivery',
        created: 'Created',
      },
    },
    files: {
      empty: 'No files for this item.',
      columns: {
        category: 'Category',
        name: 'File name',
        size: 'Size',
        uploaded: 'Uploaded',
      },
    },
    usedIn: {
      empty: 'This item is not used in any project yet.',
      columns: {
        project: 'Project',
        product: 'Product',
        description: 'Description',
        status: 'Project status',
        demanded: 'Demanded',
        fulfilled: 'Fulfilled',
        orders: 'Fulfilled orders',
      },
      noProduct: 'No product',
      noOrders: '-',
    },
    changelog: {
      empty: 'No changelog entries.',
      columns: {
        timestamp: 'Timestamp',
        user: 'User',
        message: 'Message',
      },
    },
  },
  cadClaim: {
    header: 'Managed in CAD',
    claimed:
      'PDM has claimed this item. Edit it in the SolidWorks file, not here: PDM may overwrite changes made in the web. Continue anyway?',
    claimedMany:
      'PDM has claimed {count} of the selected items. Edit them in the SolidWorks file, not here: PDM may overwrite changes made in the web. Continue anyway?',
    claimedMeanwhile:
      'PDM claimed this item while you were editing it. Edit it in the SolidWorks file, not here: PDM may overwrite changes made in the web. Continue anyway?',
    claimedMeanwhileMany:
      'PDM claimed {count} of the selected items while you were editing them. Edit them in the SolidWorks file, not here: PDM may overwrite changes made in the web. Continue anyway?',
    continue: 'Continue',
  },
}
