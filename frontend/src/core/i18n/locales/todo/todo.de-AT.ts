// Messages for todo, merged into the de-AT locale.
export default {
  title: 'Aufgaben',
  viewAll: 'Alle anzeigen',
  openCount: '{count} offen',
  andMore: '+{count} weitere',
  showAll: 'Alle werden angezeigt',
  showAllHidden: 'Alle anzeigen (+{count})',
  empty: 'Aktuell nichts zu tun.',
  emptyImportant: 'Aktuell nichts Dringendes.',
  emptyFiltered: 'Keine Kategorien ausgewählt.',
  resetFilters: 'Alle Kategorien anzeigen',
  bucketEmpty: 'Nichts vorhanden.',
  allCategories: 'Alle Kategorien',
  categories: {
    procurement: 'Beschaffung',
    shop_floor: 'Fertigung',
    planning: 'Planung',
    meetings: 'Besprechungen',
  },
  loadError: 'Aufgaben konnten nicht geladen werden.',
  buckets: {
    overdue: 'Überfällig',
    today: 'Heute',
    week: 'Diese Woche',
    blockers: 'Blocker',
  },
  tasks: {
    meetingTodo: {
      title: '{title}',
      subtitle: '{meetingNumber} {meetingName} · {scope}',
      subtitleNoScope: '{meetingNumber} {meetingName}',
    },
    collectPickup: {
      title: '{item} abholen',
      subtitle: 'Bereit bei {supplier} · {orderNumber}',
    },
    confirmPickup: {
      title: 'Abholung für {item} bestätigen',
      subtitle: 'Warten auf Bestätigung von {supplier} · {orderNumber}',
    },
    chaseDelivery: {
      title: 'Lieferung von {item} urgieren',
      subtitle: 'Überfällig von {supplier} · {orderNumber}',
    },
    chasePartialDelivery: {
      title: 'Restmenge von {item} urgieren',
      subtitle: '{delivered} von {quantity} geliefert · {supplier} · {orderNumber}',
    },
    submitOrder: {
      title: 'Bestellung {orderNumber} absenden',
      subtitle: 'Noch ein Entwurf · {supplier}',
    },
    orderDemand: {
      title: '{item} bestellen',
      subtitle: 'Projekt {project} · Menge {quantity}',
    },
    startProductionOrder: {
      title: '{lotNumber} · {partNumber} starten',
      subtitle: '{machine} · Position {position}/{count}',
    },
    productionConflict: {
      subtitle: '{lotNumber} · {orderNumber}',
    },
    planLot: {
      title: 'Los {lotNumber} planen',
      subtitle: '{partNumber} · Menge {quantity}',
    },
    resumeLot: {
      title: 'Los {lotNumber} ist angehalten',
      subtitle: '{partNumber} · Menge {quantity}',
    },
    chaseRawMaterial: {
      title: '{lotNumber} wartet auf Rohmaterial',
      subtitle: '{partNumber} · {orderNumber}',
    },
    approveLotSource: {
      title: 'Quellartikel für Los {lotNumber} freigeben',
      subtitle: '{partNumber} · Menge {quantity}',
    },
  },
}
