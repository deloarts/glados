// Messages for spreadsheetImport, merged into the de-AT locale.
export default {
  columnNames: {
    open: 'Spaltennamen',
    title: 'Spaltennamen',
    intro:
      'Die Kopfzeile der Datei braucht pro Spalte einen dieser Namen. Groß- und Kleinschreibung und zusätzliche Leerzeichen spielen keine Rolle, und eine Spalte mit anderem Namen kannst du nach dem Hochladen von Hand zuordnen. Mit * markierte Felder sind Pflicht.',
    field: 'Feld',
    names: 'Erkannte Spaltennamen',
    none: 'Keine Namen festgelegt, ordne die Spalte von Hand zu.',
    loadFailed: 'Die Spaltennamen konnten nicht geladen werden.',
  },
  errors: {
    emptyFile: 'Die Datei enthält keine Datenzeilen.',
    headerNotFound:
      'Keine Kopfzeile gefunden. Prüfe, ob die Datei eine Kopfzeile mit diesen Spalten hat: {fields}. Die Spaltennamen legst du unter Einstellungen, Datenimport fest.',
    tooManyRows: 'Die Datei hat {count} Datenzeilen, dieser Import erlaubt höchstens {limit}.',
  },
}
