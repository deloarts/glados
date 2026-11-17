// Messages for productionExceptions, merged into the en-GB locale.
export default {
  tabLabel: 'Exceptions',
  title: 'Planning Exceptions',
  count: 'No exceptions | One exception | {count} exceptions',
  noPartNumber: 'No part number',
  empty: 'Nothing needs a decision right now.',
  line: '{order} pos. {position}',
  columns: {
    rowNumber: '#',
    kind: 'Exception',
    subject: 'Lot, Order Line, Demand',
    item: 'Item',
    project: 'Project',
    detail: 'Detail',
    since: 'Since',
  },
  kind: {
    lost_at_receipt: 'Lost at receipt',
    closed_short: 'Closed short',
    lot_ended_short: 'Lot ended short',
    material_short: 'Short of material',
    late: 'Late',
  },
  family: {
    bought: 'Bought item demand #{id}',
    source: 'Raw material demand #{id}',
    made: 'Made item demand #{id}',
  },
  detail: {
    lost_at_receipt: '{quantity} {unit} of the demand are open again after pieces were lost.',
    closed_short: '{quantity} {unit} of the demand are open again after the line was closed short.',
    lot_ended_short: '{quantity} {unit} of the demand are open after the lot was force-completed.',
    material_unallocated: '{quantity} {unit} of raw material are neither ordered nor taken from stock.',
    material_undated: 'Raw material is ordered on a line without a delivery date.',
    late_planned: 'Target {target}, planned to end {end}.',
    late_passed: 'Target {target} has passed.',
  },
}
