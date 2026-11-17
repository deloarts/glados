// Messages for printers, merged into the de-AT locale.
export default {
  controls: {
    new: 'Neuer Drucker',
    search: 'Drucker suchen…',
  },
  views: {
    sortByItems: {
      nameAsc: 'Name (A → Z)',
      nameDesc: 'Name (Z → A)',
      createdDesc: 'Erstellt (neueste zuerst)',
      createdAsc: 'Erstellt (älteste zuerst)',
    },
    groupByItems: {
      kind: 'Art',
      location: 'Standort',
    },
  },
  columns: {
    name: 'Name',
    kind: 'Art',
    connection: 'Verbindung',
    location: 'Standort',
    enabled: 'Aktiviert',
    created: 'Erstellt',
    changed: 'Geändert',
    actions: 'Aktionen',
  },
  kinds: {
    zpl_label: 'ZPL-Etikett',
    ipp_document: 'IPP-Dokument',
  },
  transports: {
    raw: 'Raw (JetDirect)',
    ipp: 'IPP',
  },
  table: {
    empty: 'Noch keine Drucker vorhanden.',
  },
  filters: {
    filterBy: 'Filtern',
    any: 'Beliebig',
  },
  editPrinter: 'Drucker bearbeiten',
  testPrint: 'Testdruck',
  testPrintSent: 'Testdruck gesendet.',
  errors: {
    required: 'Bitte alle Pflichtfelder ausfüllen.',
    unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
  },
  create: {
    createTitle: 'Neuer Drucker',
    editTitle: 'Drucker bearbeiten',
    fields: {
      name: 'Name',
      internalName: 'Interner Name',
      kind: 'Art',
      host: 'Host',
      port: 'Port',
      transport: 'Übertragung',
      timeoutSeconds: 'Zeitlimit (Sekunden)',
      headDpi: 'Druckkopf-DPI',
      formatConvertFactor: 'Format-Umwandlungsfaktor',
      formatConvertFactorHint:
        'Auf den Wert setzen, mit dem die FORMAT UMWANDELN-Einstellung des Druckers eingehende Koordinaten multipliziert (1, wenn deaktiviert). Ein falscher Wert lässt Etiketten in falscher Größe drucken.',
      ippUriPath: 'IPP-URI-Pfad',
      ippUriPathHint:
        'Manche Drucker akzeptieren nur den nackten Pfad ("/") statt des üblichen "/ipp/print".',
      defaultMedia: 'Standardmedium',
      location: 'Standort',
      vendor: 'Hersteller',
      model: 'Modell',
      firmware: 'Firmware',
      boughtItems: 'Verbrauchsmaterial',
      boughtItemsPlaceholder: 'Verbrauchsmaterial auswählen…',
      enabled: 'Aktiviert',
      isDefault: 'Standarddrucker',
      note: 'Notiz',
    },
  },
  status: {
    title: 'Druckerstatus',
    identity: 'Identität',
    status: 'Status',
    errors: {
      unreachable: 'Drucker konnte nicht erreicht werden.',
    },
  },
  history: {
    menuLabel: 'Druckverlauf',
    title: 'Druckverlauf',
    empty: 'Noch keine Druckaufträge vorhanden.',
    columns: {
      created: 'Erstellt',
      classifier: 'Dokument',
      root: 'Datensatz',
      trigger: 'Auslöser',
      copies: 'Kopien',
      status: 'Status',
      actor: 'Ausgeführt von',
    },
    triggers: {
      auto: 'Automatisch',
      manual: 'Manuell',
    },
    statuses: {
      printing: 'Wird gedruckt',
      sent: 'Gesendet',
      failed: 'Fehlgeschlagen',
    },
    errors: {
      unknown: 'Der Druckverlauf konnte nicht geladen werden.',
    },
  },
}
