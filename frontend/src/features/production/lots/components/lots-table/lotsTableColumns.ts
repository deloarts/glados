// Static header metadata for the lot-level columns that share the exact
// same header shape (a rowspan-2 label over a fixed width) in every table
// mode. It is looped over in the ColumnGroup header instead of
// repeating one <Column> per field. The body cells still get their own,
// individually templated <Column> further down, since their content differs
// too much to drive from one spec.
export interface LotColumnHeaderSpec {
  key: string
  headerKey: string
  width: string
}

export const LOT_LEADING_COLUMN_SPECS: LotColumnHeaderSpec[] = [
  { key: 'rowNumber', headerKey: 'production.lots.columns.rowNumber', width: '3.5rem' },
  { key: 'lotNumber', headerKey: 'production.lots.columns.lotNumber', width: '10rem' },
  { key: 'status', headerKey: 'production.lots.columns.status', width: '9rem' },
  { key: 'priority', headerKey: 'production.lots.columns.priority', width: '8rem' },
  {
    key: 'requiredDeliveryDate',
    headerKey: 'production.lots.columns.requiredDeliveryDate',
    width: '10rem',
  },
  { key: 'project', headerKey: 'production.lots.columns.project', width: '12rem' },
  // Wide enough for the min/max pair of its range filter.
  { key: 'quantity', headerKey: 'production.lots.columns.quantity', width: '11rem' },
]

export const LOT_TRAILING_COLUMN_SPECS: LotColumnHeaderSpec[] = [
  { key: 'created', headerKey: 'production.lots.columns.created', width: '10rem' },
  { key: 'changed', headerKey: 'production.lots.columns.changed', width: '10rem' },
]
