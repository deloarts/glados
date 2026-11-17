// Messages for dashboard, merged into the de-AT locale.
export default {
  greeting: {
    morning: ['Guten Morgen', 'Einen schönen guten Morgen', 'Morgen', "Auf geht's"],
    afternoon: ['Guten Tag', 'Schönen Nachmittag', 'Hallo zusammen'],
    evening: ['Guten Abend', 'Schönen Abend', 'Willkommen zurück'],
  },
  stats: {
    inProcess: 'In Bearbeitung',
    overdueToday: 'Überfällig + Heute',
    activeLots: 'Aktive Lose',
    unreadNotifications: 'Ungelesene Hinweise',
    openDemands: 'Offene Bedarfe',
    ordersLast30Days: 'Bestellungen (30 Tage)',
    tasksDueNow: 'Fällige Aufgaben',
  },
  shopFloor: {
    title: 'Fertigung heute',
    empty: 'Nichts überfällig oder heute fällig. Alles ruhig.',
  },
  alerts: {
    title: 'Hinweise',
    markAllRead: 'Alle als gelesen markieren',
    empty: 'Keine Benachrichtigungen',
  },
  wip: {
    title: 'In Arbeit',
    empty: 'Aktuell sind keine Lose in Produktion.',
  },
  demandPipeline: {
    title: 'Bedarfsverlauf',
    made: 'Fertigungsartikel',
    bought: 'Kaufartikel',
    source: 'Rohblock',
    fulfilled: '{count} erfüllt',
  },
  quickLinks: {
    title: 'Schnellzugriff',
  },
  spending: {
    title: 'Ausgaben der letzten 30 Tage',
    spent: 'Ausgegeben',
    orders: 'Bestellungen',
    empty: 'In den letzten 30 Tagen wurden keine Bestellungen aufgegeben.',
  },
  recentItems: {
    title: 'Zuletzt hinzugefügte Artikel',
    empty: 'Keine zuletzt hinzugefügten Artikel.',
    made: 'Fertigung',
    bought: 'Kauf',
  },
}
