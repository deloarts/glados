// Messages for productionExceptions, merged into the de-AT locale.
export default {
  tabLabel: 'Ausnahmen',
  title: 'Planungsausnahmen',
  count: 'Keine Ausnahmen | Eine Ausnahme | {count} Ausnahmen',
  noPartNumber: 'Keine Teilenummer',
  empty: 'Gerade braucht nichts eine Entscheidung.',
  line: '{order} Pos. {position}',
  columns: {
    rowNumber: '#',
    kind: 'Ausnahme',
    subject: 'Los, Bestellposition, Bedarf',
    item: 'Artikel',
    project: 'Projekt',
    detail: 'Details',
    since: 'Seit',
  },
  kind: {
    lost_at_receipt: 'Beim Wareneingang verloren',
    closed_short: 'Restmenge ausgebucht',
    lot_ended_short: 'Los mit Fehlmenge beendet',
    material_short: 'Material fehlt',
    late: 'Verspätet',
  },
  family: {
    bought: 'Zukaufteile-Bedarf #{id}',
    source: 'Rohmaterialbedarf #{id}',
    made: 'Fertigungsteile-Bedarf #{id}',
  },
  detail: {
    lost_at_receipt: '{quantity} {unit} des Bedarfs sind wieder offen, weil Teile verloren gingen.',
    closed_short: '{quantity} {unit} des Bedarfs sind wieder offen, weil die Restmenge ausgebucht wurde.',
    lot_ended_short: '{quantity} {unit} des Bedarfs sind offen, weil das Los zwangsweise abgeschlossen wurde.',
    material_unallocated: '{quantity} {unit} Rohmaterial sind weder bestellt noch aus dem Lager genommen.',
    material_undated: 'Rohmaterial ist auf einer Position ohne Liefertermin bestellt.',
    late_planned: 'Ziel {target}, geplantes Ende {end}.',
    late_passed: 'Ziel {target} ist überschritten.',
  },
}
