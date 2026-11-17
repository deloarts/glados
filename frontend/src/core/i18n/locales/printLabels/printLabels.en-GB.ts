// Messages for printLabels, merged into the en-GB locale.
export default {
  controls: {
    search: 'Search labels…',
    disableAllPrinters: 'Disable All Printers',
    disableAllPrintersConfirm:
      'Disable every printer? No label or docket will print, anywhere, until they are re-enabled from /resources/printers.',
    disableAllPrintersDone:
      'No printers disabled. | Disabled 1 printer. | Disabled {count} printers.',
    disableAutoPrint: 'Disable Auto-Print',
    disableAutoPrintConfirm:
      'Turn off auto-print for every label template? Manual printing is unaffected.',
    disableAutoPrintDone:
      'No labels had auto-print disabled. | Disabled auto-print on 1 label. | Disabled auto-print on {count} labels.',
  },
  columns: {
    classifier: 'Label',
    trigger: 'Trigger',
    copiesRule: 'Copies Rule',
    autoPrint: 'Auto-print',
    printer: 'Printer',
    created: 'Created',
    changed: 'Changed',
    enabled: 'Enabled',
    actions: 'Actions',
  },
  classifiers: {
    source_item_label: 'Source Item Label',
    bought_item_label: 'Bought Item Label',
    made_item_label: 'Made Item Label',
    production_order_label: 'Production Order Label',
    lot_label: 'Lot Label',
    scrap_tag: 'Scrap Tag',
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
  manualOnlyHint: 'This label has no lifecycle trigger, it can only be printed manually.',
  editTemplate: 'Edit Label',
  previewAction: 'Preview',
  reset: 'Clear Content',
  resetConfirm: 'Clear "{name}"\'s content? Your changes will be lost.',
  resetDone: 'Content cleared.',
  table: {
    empty: 'No labels yet.',
  },
  errors: {
    unknown: 'Something went wrong. Please try again.',
  },
  editor: {
    fields: {
      trigger: 'Trigger',
      printer: 'Printer',
      autoPrint: 'Auto-print',
      enabled: 'Enabled',
      copiesRule: 'Copies Rule',
      copiesFixed: 'Fixed Copies',
      maxCopies: 'Max Copies',
      maxCopiesHint: 'Hard cap on any single print job, however copies are resolved.',
      source: 'ZPL Source',
      upload: 'Upload',
      fieldMap: 'Field Map',
      fieldMapEmpty: 'No {placeholder} tokens found in the ZPL source yet.',
      fieldMapPlaceholder: 'Select a source…',
      note: 'Note',
    },
    preview: {
      recordId: 'Record ID',
      recordIdHint: 'The ID of a real record to render the label against.',
      empty: 'Enter a record ID above to preview.',
    },
    errors: {
      unknown: 'Something went wrong. Please try again.',
      unmappedPlaceholders:
        'No unmapped placeholders in the field map | 1 unmapped placeholder in the field map: {names} | {count} unmapped placeholders in the field map: {names}',
    },
  },
  preview: {
    errors: {
      unknown: 'Could not render the preview.',
    },
  },
}
