// Messages for printDockets, merged into the en-GB locale.
export default {
  controls: {
    search: 'Search dockets…',
    disableAllPrinters: 'Disable All Printers',
    disableAllPrintersConfirm:
      'Disable every printer? No label or docket will print, anywhere, until they are re-enabled from /resources/printers.',
    disableAllPrintersDone:
      'No printers disabled. | Disabled 1 printer. | Disabled {count} printers.',
    disableAutoPrint: 'Disable Auto-Print',
    disableAutoPrintConfirm:
      'Turn off auto-print for every docket template? Manual printing is unaffected.',
    disableAutoPrintDone:
      'No dockets had auto-print disabled. | Disabled auto-print on 1 docket. | Disabled auto-print on {count} dockets.',
  },
  columns: {
    classifier: 'Docket',
    trigger: 'Trigger',
    copiesRule: 'Copies Rule',
    autoPrint: 'Auto-print',
    printer: 'Printer',
    pageSize: 'Page Size',
    created: 'Created',
    changed: 'Changed',
    enabled: 'Enabled',
    actions: 'Actions',
  },
  classifiers: {
    order_docket: 'Order Docket',
    lot_docket: 'Lot Docket',
    production_order_docket: 'Production Order Docket',
    made_item_docket: 'Made Item Docket',
    bought_item_docket: 'Bought Item Docket',
    source_item_docket: 'Source Item Docket',
  },
  pageSizes: {
    a4: 'A4',
    a4_aligned: 'A4 (aligned)',
    a5: 'A5',
  },
  triggers: {
    source_item_delivered: 'Source item delivered',
    bought_item_delivered: 'Bought item delivered',
    made_item_completed: 'Made item completed (lot completed)',
    production_order_created: 'Production order created',
    production_order_started: 'Production order started',
    production_order_completion_recorded: 'Production order completion recorded',
    production_order_completed: 'Production order completed',
    lot_created: 'Lot created',
    lot_completed: 'Lot completed',
    pieces_scrapped: 'Pieces scrapped',
  },
  copiesRules: {
    fixed: 'Fixed',
    per_event_quantity: 'Per occurrence quantity',
    per_lot_quantity: 'Per lot quantity',
  },
  manualOnly: 'Manual only',
  manualOnlyHint: 'This docket has no lifecycle trigger, it can only be printed manually.',
  editTemplate: 'Edit Docket',
  previewAction: 'Preview',
  reset: 'Clear Content',
  resetConfirm: 'Clear "{name}"\'s content? Your changes will be lost.',
  resetDone: 'Content cleared.',
  table: {
    empty: 'No dockets yet.',
  },
  errors: {
    unknown: 'Something went wrong. Please try again.',
  },
  download: {
    action: 'Download PDF',
    errors: {
      unknown: 'Could not download the docket.',
    },
  },
  editor: {
    fields: {
      trigger: 'Trigger',
      printer: 'Printer',
      paper: 'Paper',
      paperA4: 'A4 (centred with cut marks)',
      paperA4Aligned: 'A4 aligned (cut in half for an A5 docket)',
      paperA5: 'A5 (1:1)',
      autoPrint: 'Auto-print',
      enabled: 'Enabled',
      copiesRule: 'Copies Rule',
      copiesFixed: 'Fixed Copies',
      maxCopies: 'Max Copies',
      maxCopiesHint: 'Hard cap on any single print job, however copies are resolved.',
      source: 'Block Spec (JSON)',
      upload: 'Upload',
      fieldMap: 'Field Map',
      fieldMapEmpty: 'No block fields found in the JSON source yet.',
      fieldMapPlaceholder: 'Select a source…',
      note: 'Note',
    },
    preview: {
      recordId: 'Record ID',
      recordIdHint: 'The ID of a real record to render the docket against.',
      empty: 'Enter a record ID above to preview.',
    },
    errors: {
      unknown: 'Something went wrong. Please try again.',
      invalidJson: 'This is not valid JSON.',
      unmappedPlaceholders:
        'No unmapped fields in the field map | 1 unmapped field in the field map: {names} | {count} unmapped fields in the field map: {names}',
    },
  },
  preview: {
    errors: {
      unknown: 'Could not render the preview.',
    },
  },
}
