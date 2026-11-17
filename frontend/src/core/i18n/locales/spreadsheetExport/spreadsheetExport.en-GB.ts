// Messages for spreadsheetExport, merged into the en-GB locale.
export default {
  export: 'Export',
  scope: {
    filtered: 'All Filtered Rows ({count})',
    selected: 'Selected Rows ({count})',
  },
  progress: 'Exporting {loaded} of {total}',
  confirm: {
    header: 'Large Export',
    message: 'This export contains {count} rows and may take a moment. Export anyway?',
    accept: 'Export',
  },
  tooManyRows: {
    summary: 'Too many rows',
    detail: 'The filter matches {count} rows, an export takes at most {limit}. Narrow the filter and try again.',
  },
  failed: 'Export failed',
  columns: {
    link: 'Link',
    createdBy: 'Created By',
    changedBy: 'Changed By',
    unit: 'Unit',
    customer: 'Customer',
    projectDescription: 'Project Description',
    note: 'Note',
    itemLink: 'Item Link',
  },
}
