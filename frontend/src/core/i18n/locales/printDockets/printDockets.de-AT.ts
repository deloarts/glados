// Messages for printDockets, merged into the de-AT locale.
export default {
  controls: {
    search: 'Laufzettel suchen…',
    disableAllPrinters: 'Alle Drucker deaktivieren',
    disableAllPrintersConfirm:
      'Jeden Drucker deaktivieren? Es wird nirgendwo mehr etwas gedruckt, weder Etikett noch Laufzettel, bis sie unter /resources/printers wieder aktiviert werden.',
    disableAllPrintersDone:
      'Keine Drucker deaktiviert. | 1 Drucker deaktiviert. | {count} Drucker deaktiviert.',
    disableAutoPrint: 'Auto-Druck deaktivieren',
    disableAutoPrintConfirm:
      'Auto-Druck für jede Laufzettelvorlage deaktivieren? Manueller Druck ist davon nicht betroffen.',
    disableAutoPrintDone:
      'Für keine Laufzettel wurde Auto-Druck deaktiviert. | Auto-Druck für 1 Laufzettel deaktiviert. | Auto-Druck für {count} Laufzettel deaktiviert.',
  },
  columns: {
    classifier: 'Laufzettel',
    trigger: 'Auslöser',
    copiesRule: 'Kopienregel',
    autoPrint: 'Auto-Druck',
    printer: 'Drucker',
    pageSize: 'Papiergröße',
    created: 'Erstellt',
    changed: 'Geändert',
    enabled: 'Aktiviert',
    actions: 'Aktionen',
  },
  classifiers: {
    order_docket: 'Bestellung-Laufzettel',
    lot_docket: 'Los-Laufzettel',
    production_order_docket: 'Fertigungsauftrag-Laufzettel',
    made_item_docket: 'Fertigartikel-Laufzettel',
    bought_item_docket: 'Kaufartikel-Laufzettel',
    source_item_docket: 'Rohblock-Laufzettel',
  },
  pageSizes: {
    a4: 'A4',
    a4_aligned: 'A4 (ausgerichtet)',
    a5: 'A5',
  },
  triggers: {
    source_item_delivered: 'Rohblock geliefert',
    bought_item_delivered: 'Kaufartikel geliefert',
    made_item_completed: 'Fertigungsteil fertiggestellt (Los abgeschlossen)',
    production_order_created: 'Fertigungsauftrag erstellt',
    production_order_started: 'Fertigungsauftrag gestartet',
    production_order_completion_recorded: 'Fertigungsauftrag-Fertigmeldung erfasst',
    production_order_completed: 'Fertigungsauftrag abgeschlossen',
    lot_created: 'Los erstellt',
    lot_completed: 'Los abgeschlossen',
    pieces_scrapped: 'Teile verschrottet',
  },
  copiesRules: {
    fixed: 'Fest',
    per_event_quantity: 'Pro Vorgangsmenge',
    per_lot_quantity: 'Pro Losmenge',
  },
  manualOnly: 'Nur manuell',
  manualOnlyHint:
    'Dieser Laufzettel hat keinen Lebenszyklus-Auslöser und kann nur manuell gedruckt werden.',
  editTemplate: 'Laufzettel bearbeiten',
  previewAction: 'Vorschau',
  reset: 'Inhalt löschen',
  resetConfirm: 'Inhalt von "{name}" löschen? Deine Änderungen gehen verloren.',
  resetDone: 'Inhalt gelöscht.',
  table: {
    empty: 'Noch keine Laufzettel vorhanden.',
  },
  errors: {
    unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
  },
  download: {
    action: 'PDF herunterladen',
    errors: {
      unknown: 'Der Laufzettel konnte nicht heruntergeladen werden.',
    },
  },
  editor: {
    fields: {
      trigger: 'Auslöser',
      printer: 'Drucker',
      paper: 'Papier',
      paperA4: 'A4 (zentriert mit Schnittmarken)',
      paperA4Aligned: 'A4 ausgerichtet (in der Hälfte schneiden für A5-Laufzettel)',
      paperA5: 'A5 (1:1)',
      autoPrint: 'Auto-Druck',
      enabled: 'Aktiviert',
      copiesRule: 'Kopienregel',
      copiesFixed: 'Feste Kopienanzahl',
      maxCopies: 'Max. Kopien',
      maxCopiesHint:
        'Obergrenze für jeden einzelnen Druckauftrag, unabhängig davon, wie die Kopienanzahl ermittelt wird.',
      source: 'Block-Spezifikation (JSON)',
      upload: 'Hochladen',
      fieldMap: 'Feldzuordnung',
      fieldMapEmpty: 'Noch keine Blockfelder in der JSON-Quelle gefunden.',
      fieldMapPlaceholder: 'Quelle auswählen…',
      note: 'Notiz',
    },
    preview: {
      recordId: 'Datensatz-ID',
      recordIdHint: 'Die ID eines echten Datensatzes, gegen den der Laufzettel gerendert wird.',
      empty: 'Gib oben eine Datensatz-ID ein, um eine Vorschau anzuzeigen.',
    },
    errors: {
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
      invalidJson: 'Dies ist kein gültiges JSON.',
      unmappedPlaceholders:
        'Keine nicht zugeordneten Felder in der Feldzuordnung | 1 nicht zugeordnetes Feld in der Feldzuordnung: {names} | {count} nicht zugeordnete Felder in der Feldzuordnung: {names}',
    },
  },
  preview: {
    errors: {
      unknown: 'Die Vorschau konnte nicht gerendert werden.',
    },
  },
}
