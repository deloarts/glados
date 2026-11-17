// Messages for procurement, merged into the de-AT locale.
export default {
  sections: {
    orders: 'Bestellungen',
    quotes: 'Angebote',
    boughtItemsDemand: 'Zukaufteile Bedarf',
    madeItemsDemand: 'Fertigungsteile Bedarf',
    sourceItemsDemand: 'Rohblock Bedarf',
  },
  timeline: {
    empty: 'Noch keine Bestellungen mit Terminen vorhanden.',
    columns: {
      orderNumber: 'Bestellnummer',
      status: 'Status',
      orderDate: 'Bestelldatum',
      durationDays: 'Dauer (Tage)',
    },
  },
  unitMismatchSummary:
    'Eine Bestellposition dieses Bedarfs ist in einer anderen Einheit. Die Mengen zählen eins zu eins, nichts wird umgerechnet.',
  unitMismatch:
    'Der Bedarf ist in {demand}, die Bestellposition in {line}. Die Mengen zählen eins zu eins, nichts wird umgerechnet.',
}
