// Messages for printers, merged into the en-GB locale.
export default {
  controls: {
    new: 'New Printer',
    search: 'Search printers…',
  },
  views: {
    sortByItems: {
      nameAsc: 'Name (A → Z)',
      nameDesc: 'Name (Z → A)',
      createdDesc: 'Created (newest first)',
      createdAsc: 'Created (oldest first)',
    },
    groupByItems: {
      kind: 'Kind',
      location: 'Location',
    },
  },
  columns: {
    name: 'Name',
    kind: 'Kind',
    connection: 'Connection',
    location: 'Location',
    enabled: 'Enabled',
    created: 'Created',
    changed: 'Changed',
    actions: 'Actions',
  },
  kinds: {
    zpl_label: 'ZPL Label',
    ipp_document: 'IPP Document',
  },
  transports: {
    raw: 'Raw (JetDirect)',
    ipp: 'IPP',
  },
  table: {
    empty: 'No printers yet.',
  },
  filters: {
    filterBy: 'Filter',
    any: 'Any',
  },
  editPrinter: 'Edit Printer',
  testPrint: 'Test Print',
  testPrintSent: 'Test print sent.',
  errors: {
    required: 'Please fill in all required fields.',
    unknown: 'Something went wrong. Please try again.',
  },
  create: {
    createTitle: 'New Printer',
    editTitle: 'Edit Printer',
    fields: {
      name: 'Name',
      internalName: 'Internal Name',
      kind: 'Kind',
      host: 'Host',
      port: 'Port',
      transport: 'Transport',
      timeoutSeconds: 'Timeout (seconds)',
      headDpi: 'Head DPI',
      formatConvertFactor: 'Format Convert Factor',
      formatConvertFactorHint:
        "Set this to whatever the printer's own front-panel Format Convert setting multiplies incoming coordinates by (1 if it is off). Getting this wrong is what makes a label print at the wrong size.",
      ippUriPath: 'IPP URI Path',
      ippUriPathHint:
        'Some printers only accept the bare root ("/") rather than the usual "/ipp/print".',
      defaultMedia: 'Default Media',
      location: 'Location',
      vendor: 'Vendor',
      model: 'Model',
      firmware: 'Firmware',
      boughtItems: 'Consumables',
      boughtItemsPlaceholder: 'Select consumables…',
      enabled: 'Enabled',
      isDefault: 'Default Printer',
      note: 'Note',
    },
  },
  status: {
    title: 'Printer Status',
    identity: 'Identity',
    status: 'Status',
    errors: {
      unreachable: 'Could not reach the printer.',
    },
  },
  history: {
    menuLabel: 'Print History',
    title: 'Print History',
    empty: 'No print jobs yet.',
    columns: {
      created: 'Created',
      classifier: 'Document',
      root: 'Record',
      trigger: 'Trigger',
      copies: 'Copies',
      status: 'Status',
      actor: 'Actor',
    },
    triggers: {
      auto: 'Auto',
      manual: 'Manual',
    },
    statuses: {
      printing: 'Printing',
      sent: 'Sent',
      failed: 'Failed',
    },
    errors: {
      unknown: 'Could not load print history.',
    },
  },
}
