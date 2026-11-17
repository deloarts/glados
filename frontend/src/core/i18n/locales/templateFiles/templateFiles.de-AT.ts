// Messages for importing and exporting template files in the settings editors, merged into the de-AT locale.
export default {
  importFile: 'Aus Datei importieren',
  exportFile: 'In Datei exportieren',
  imported: '{files} geladen',
  importedReview: 'Prüf die Werte und speichere, um sie zu übernehmen.',
  importedIgnored: 'Prüf die Werte und speichere, um sie zu übernehmen. Nicht verwendet: {keys}.',
  importFailed: 'Import fehlgeschlagen',
  errors: {
    invalidJson: '{file} ist keine gültige JSON-Datei.',
    notTemplate: '{file} ist keine Glados-Vorlagendatei.',
    wrongKind: '{file} enthält eine andere Art von Vorlage ({detail}).',
    unsupportedVersion: '{file} verwendet die Formatversion {detail}, die diese Glados-Version nicht lesen kann.',
    invalidContent: '{file} hat einen ungültigen Wert bei „{detail}“.',
    wrongTarget: '{file} gehört zu {detail}, nicht zu dieser Vorlage.',
    readFailed: '{file} konnte nicht gelesen werden.',
  },
  mail: {
    importTemplates: 'Vorlagen importieren',
    dialogTitle: 'Mailvorlagen importieren',
    intro:
      'Wähl eine oder mehrere HTML-Dateien, die nach Vorlage und Sprache benannt sind, etwa welcome.deAT.html. Der Titel jeder Datei wird zum Betreff.',
    columns: {
      file: 'Datei',
      template: 'Vorlage',
      language: 'Sprache',
      status: 'Status',
    },
    status: {
      new: 'Neu',
      replaces: 'Ersetzt die aktuelle Vorlage',
      badName: 'Name nicht erkannt',
      unknownKind: 'Unbekannte Vorlage',
      unknownLanguage: 'Sprache nicht aktiviert',
      duplicate: 'Doppelt gewählt, die letzte zählt',
    },
    importAction: 'Eine Vorlage importieren | {count} Vorlagen importieren',
    importedCount: 'Eine Mailvorlage importiert. | {count} Mailvorlagen importiert.',
    nothingToImport: 'Keine der gewählten Dateien kann importiert werden.',
    saveFailed: 'Die Vorlagen für {kind} konnten nicht gespeichert werden.',
  },
  pdm: {
    importVariableMaps: 'Variablenzuordnung importieren',
    exportVariableMaps: 'Variablenzuordnung exportieren',
  },
}
