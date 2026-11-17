// Messages for pdmPreview, merged into the en-GB locale.
export default {
  controls: {
    toggle: 'PDM Preview ({count})',
  },
  panel: {
    empty: 'No preview files',
    pdmOnly: 'Only in PDM so far',
    columns: {
      partNumber: 'Part number',
      revision: 'Revision',
      articleName: 'Article Name',
      file: 'File',
      version: 'Version',
      state: 'State',
      modifiedAt: 'Modified',
      syncState: 'Status',
    },
    syncStates: {
      pending: 'Pending',
      ingested: 'Ingested',
      skipped: 'Skipped',
      missing: 'Missing',
      conflict: 'Conflict',
      error: 'Error',
    },
  },
  badge: {
    label: 'Preview v{version} · {state}',
    tooltip: 'Modified {date}',
  },
}
