// Messages for printLabels, merged into the de-AT locale.
export default {
  controls: {
    search: 'Etiketten suchen…',
    disableAllPrinters: 'Alle Drucker deaktivieren',
    disableAllPrintersConfirm:
      'Jeden Drucker deaktivieren? Es wird nirgendwo mehr etwas gedruckt, weder Etikett noch Laufzettel, bis sie unter /resources/printers wieder aktiviert werden.',
    disableAllPrintersDone:
      'Keine Drucker deaktiviert. | 1 Drucker deaktiviert. | {count} Drucker deaktiviert.',
    disableAutoPrint: 'Auto-Druck deaktivieren',
    disableAutoPrintConfirm:
      'Auto-Druck für jede Etikettenvorlage deaktivieren? Manueller Druck ist davon nicht betroffen.',
    disableAutoPrintDone:
      'Für keine Etiketten wurde Auto-Druck deaktiviert. | Auto-Druck für 1 Etikett deaktiviert. | Auto-Druck für {count} Etiketten deaktiviert.',
  },
  columns: {
    classifier: 'Etikett',
    trigger: 'Auslöser',
    copiesRule: 'Kopienregel',
    autoPrint: 'Auto-Druck',
    printer: 'Drucker',
    created: 'Erstellt',
    changed: 'Geändert',
    enabled: 'Aktiviert',
    actions: 'Aktionen',
  },
  classifiers: {
    source_item_label: 'Rohblock-Etikett',
    bought_item_label: 'Kaufartikel-Etikett',
    made_item_label: 'Fertigungsteil-Etikett',
    production_order_label: 'Fertigungsauftrag-Etikett',
    lot_label: 'Los-Etikett',
    scrap_tag: 'Ausschuss-Etikett',
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
    'Dieses Etikett hat keinen Lebenszyklus-Auslöser und kann nur manuell gedruckt werden.',
  editTemplate: 'Etikett bearbeiten',
  previewAction: 'Vorschau',
  reset: 'Inhalt löschen',
  resetConfirm: 'Inhalt von "{name}" löschen? Deine Änderungen gehen verloren.',
  resetDone: 'Inhalt gelöscht.',
  table: {
    empty: 'Noch keine Etiketten vorhanden.',
  },
  errors: {
    unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
  },
  editor: {
    fields: {
      trigger: 'Auslöser',
      printer: 'Drucker',
      autoPrint: 'Auto-Druck',
      enabled: 'Aktiviert',
      copiesRule: 'Kopienregel',
      copiesFixed: 'Feste Kopienanzahl',
      maxCopies: 'Max. Kopien',
      maxCopiesHint:
        'Obergrenze für jeden einzelnen Druckauftrag, unabhängig davon, wie die Kopienanzahl ermittelt wird.',
      source: 'ZPL-Quelltext',
      upload: 'Hochladen',
      fieldMap: 'Feldzuordnung',
      fieldMapEmpty: 'Noch keine {placeholder}-Platzhalter im ZPL-Quelltext gefunden.',
      fieldMapPlaceholder: 'Quelle auswählen…',
      note: 'Notiz',
    },
    preview: {
      recordId: 'Datensatz-ID',
      recordIdHint: 'Die ID eines echten Datensatzes, gegen den das Etikett gerendert wird.',
      empty: 'Gib oben eine Datensatz-ID ein, um eine Vorschau anzuzeigen.',
    },
    errors: {
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
      unmappedPlaceholders:
        'Keine nicht zugeordneten Platzhalter in der Feldzuordnung | 1 nicht zugeordneter Platzhalter in der Feldzuordnung: {names} | {count} nicht zugeordnete Platzhalter in der Feldzuordnung: {names}',
    },
  },
  preview: {
    errors: {
      unknown: 'Die Vorschau konnte nicht gerendert werden.',
    },
  },
}
