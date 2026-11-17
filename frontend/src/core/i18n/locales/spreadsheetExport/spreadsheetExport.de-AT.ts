// Messages for spreadsheetExport, merged into the de-AT locale.
export default {
  export: 'Exportieren',
  scope: {
    filtered: 'Alle gefilterten Zeilen ({count})',
    selected: 'Ausgewählte Zeilen ({count})',
  },
  progress: 'Exportiere {loaded} von {total}',
  confirm: {
    header: 'Großer Export',
    message: 'Der Export umfasst {count} Zeilen und kann einen Moment dauern. Trotzdem exportieren?',
    accept: 'Exportieren',
  },
  tooManyRows: {
    summary: 'Zu viele Zeilen',
    detail: 'Der Filter trifft {count} Zeilen, ein Export umfasst höchstens {limit}. Schränk den Filter ein und versuch es nochmal.',
  },
  failed: 'Export fehlgeschlagen',
  columns: {
    link: 'Link',
    createdBy: 'Erstellt von',
    changedBy: 'Geändert von',
    unit: 'Einheit',
    customer: 'Kunde',
    projectDescription: 'Projektbeschreibung',
    note: 'Notiz',
    itemLink: 'Link zum Teil',
  },
}
