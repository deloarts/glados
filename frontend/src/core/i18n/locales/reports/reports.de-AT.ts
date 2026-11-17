// Messages for PDF reports and their export dialog, merged into the de-AT locale.
export default {
  export: {
    title: 'Bericht exportieren',
    language: 'Sprache',
    download: 'PDF herunterladen',
    printHeading: 'Drucken',
    printer: 'Drucker',
    copies: 'Kopien',
    twoSided: 'Beidseitig drucken',
    twoSidedRaw: 'Dieser Drucker ist ohne IPP angebunden und druckt daher immer einseitig.',
    print: 'Drucken',
    unsaved:
      'Nur gespeicherte Datensätze können an einen Drucker geschickt werden. Speichere zuerst, oder lade das PDF herunter und drucke es selbst.',
    noPrinters: 'Es ist kein Dokumentdrucker eingerichtet. Lade stattdessen das PDF herunter.',
    printSent: 'An {printer} gesendet.',
    printSubstituted:
      'An {printer} gesendet, aber der Drucker hat nicht alle Einstellungen übernommen und druckt eventuell nur einseitig.',
    printFailed: 'Der Bericht konnte nicht gedruckt werden.',
    journalFailed: 'Das PDF wurde heruntergeladen, aber der Download konnte nicht im Exportjournal vermerkt werden.',
    renderFailed: 'Das PDF konnte nicht erstellt werden.',
  },
  document: {
    page: 'Seite {page} von {pages}',
    exportedBy: 'Exportiert von {name}',
    exportedAt: 'Exportiert am {date}',
    copyNotice: 'Ausgedruckte Kopie, prüfe über den QR-Code die aktuelle Revision',
  },
  distribution: {
    title: 'Verteilung',
    empty: 'Von diesem Dokument wurde noch kein Bericht heruntergeladen oder gedruckt.',
    failed: 'Die Verteilung konnte nicht geladen werden.',
    when: 'Wann',
    what: 'Was',
    revision: 'Revision',
    language: 'Sprache',
    file: 'Datei',
    downloaded: 'Heruntergeladen',
    printed: 'Gedruckt, {copies}×',
  },
  classifiers: {
    calculation_report: 'Berechnungsbericht',
    checklist_report: 'Checklistenbericht',
    inspection_report: 'Prüfbericht',
    meeting_notes: 'Besprechungsprotokoll',
  },
}
