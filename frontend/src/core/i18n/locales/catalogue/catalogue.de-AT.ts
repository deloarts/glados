// Messages for catalogue, merged into the de-AT locale.
export default {
  itemDetail: {
    notFound: 'Dieser Artikel existiert nicht oder wurde gelöscht.',
    loadError: 'Der Artikel konnte nicht geladen werden.',
    sectionError: 'Dieser Abschnitt konnte nicht geladen werden.',
    truncated: 'Es werden nur die ersten {limit} Einträge angezeigt.',
    actions: {
      edit: 'Artikel bearbeiten',
      createDemand: 'Bedarf anlegen',
      addToOrder: 'Zur Bestellung hinzufügen',
      print: 'Drucken',
      printLabel: 'Etikett',
      printDocket: 'Laufzettel',
    },
    media: {
      openFile: '{name} öffnen',
      placeholderName: '3D-Vorschau',
    },
    print: {
      labelSent: 'Etikett an Drucker gesendet.',
      labelFailed: 'Etikett konnte nicht gedruckt werden.',
      docketSent: 'Laufzettel an Drucker gesendet.',
      docketFailed: 'Laufzettel konnte nicht gedruckt werden.',
    },
    cards: {
      item: 'Artikel',
      files: 'Dateien',
      demands: 'Bedarfe',
      orders: 'Bestellungen',
      lots: 'Lose',
      usedIn: 'Verwendung',
      changelog: 'Änderungsprotokoll',
      processes: 'Arbeitsplan',
    },
    demands: {
      empty: 'Keine Bedarfe für diesen Artikel.',
      columns: {
        id: 'Bedarf',
        status: 'Status',
        quantity: 'Menge',
        project: 'Projekt',
        desiredDelivery: 'Wunschtermin',
        created: 'Erstellt',
        alteration: 'Änderung',
        lot: 'Los',
      },
    },
    orders: {
      empty: 'Dieser Artikel wurde noch nicht bestellt.',
      columns: {
        orderNumber: 'Bestellung',
        supplier: 'Lieferant',
        orderStatus: 'Bestellstatus',
        quantity: 'Menge',
        itemStatus: 'Positionsstatus',
        project: 'Projekt',
        orderedDate: 'Bestellt',
        deliveryDate: 'Geliefert',
        price: 'Preis',
      },
    },
    lots: {
      empty: 'Keine Lose für diesen Artikel.',
      columns: {
        lotNumber: 'Los',
        status: 'Status',
        quantity: 'Fertig / Menge',
        project: 'Projekt',
        requiredDelivery: 'Benötigt bis',
        created: 'Erstellt',
      },
    },
    files: {
      empty: 'Keine Dateien für diesen Artikel.',
      columns: {
        category: 'Kategorie',
        name: 'Dateiname',
        size: 'Größe',
        uploaded: 'Hochgeladen',
      },
    },
    usedIn: {
      empty: 'Dieser Artikel wird noch in keinem Projekt verwendet.',
      columns: {
        project: 'Projekt',
        product: 'Produkt',
        description: 'Beschreibung',
        status: 'Projektstatus',
        demanded: 'Bedarf',
        fulfilled: 'Erfüllt',
        orders: 'Erfüllte Bestellungen',
      },
      noProduct: 'Kein Produkt',
      noOrders: '-',
    },
    changelog: {
      empty: 'Keine Änderungen erfasst.',
      columns: {
        timestamp: 'Zeitstempel',
        user: 'Benutzer',
        message: 'Änderung',
      },
    },
  },
  cadClaim: {
    header: 'In CAD verwaltet',
    claimed:
      'PDM hat dieses Teil übernommen. Bearbeite es in der SolidWorks-Datei, nicht hier: PDM kann Änderungen aus dem Web überschreiben. Trotzdem fortfahren?',
    claimedMany:
      'PDM hat {count} der ausgewählten Teile übernommen. Bearbeite sie in der SolidWorks-Datei, nicht hier: PDM kann Änderungen aus dem Web überschreiben. Trotzdem fortfahren?',
    claimedMeanwhile:
      'PDM hat dieses Teil übernommen, während du es bearbeitet hast. Bearbeite es in der SolidWorks-Datei, nicht hier: PDM kann Änderungen aus dem Web überschreiben. Trotzdem fortfahren?',
    claimedMeanwhileMany:
      'PDM hat {count} der ausgewählten Teile übernommen, während du sie bearbeitet hast. Bearbeite sie in der SolidWorks-Datei, nicht hier: PDM kann Änderungen aus dem Web überschreiben. Trotzdem fortfahren?',
    continue: 'Fortfahren',
  },
}
