// Messages for pdmPreview, merged into the de-AT locale.
export default {
  controls: {
    toggle: 'PDM-Vorschau ({count})',
  },
  panel: {
    empty: 'Keine Vorschau-Dateien',
    pdmOnly: 'Bisher nur in PDM vorhanden',
    columns: {
      partNumber: 'Artikelnummer',
      revision: 'Revision',
      articleName: 'Artikelbezeichnung',
      file: 'Datei',
      version: 'Version',
      state: 'Zustand',
      modifiedAt: 'Geändert',
      syncState: 'Status',
    },
    syncStates: {
      pending: 'Ausstehend',
      ingested: 'Übernommen',
      skipped: 'Übersprungen',
      missing: 'Fehlend',
      conflict: 'Konflikt',
      error: 'Fehler',
    },
  },
  badge: {
    label: 'Vorschau v{version} · {state}',
    tooltip: 'Geändert am {date}',
  },
}
