export type StepCellKind =
  | 'method'
  | 'status'
  | 'setup'
  | 'perPiece'
  | 'plannedStart'
  | 'plannedDate'
  | 'deliveryDate'
  | 'note'

export interface StepCellSpec {
  kind: StepCellKind
  headerKey: string
  headerWidth: string
  bodyWidth: string
}

// Step cell order, labels and widths shared by Widescreen and Column Mode.
export const STEP_CELL_SPECS: StepCellSpec[] = [
  {
    kind: 'method',
    headerKey: 'production.lots.columns.stepMethod',
    headerWidth: '12rem',
    bodyWidth: '12rem',
  },
  {
    kind: 'status',
    headerKey: 'production.lots.columns.stepStatus',
    headerWidth: '9rem',
    bodyWidth: '9rem',
  },
  {
    kind: 'setup',
    headerKey: 'production.lots.columns.stepSetup',
    headerWidth: '6rem',
    bodyWidth: '6rem',
  },
  {
    kind: 'perPiece',
    headerKey: 'production.lots.columns.stepPerPiece',
    headerWidth: '6rem',
    bodyWidth: '6rem',
  },
  {
    kind: 'plannedStart',
    headerKey: 'production.lots.columns.stepPlannedStart',
    headerWidth: '8rem',
    bodyWidth: '8rem',
  },
  {
    kind: 'plannedDate',
    headerKey: 'production.lots.columns.stepPlannedDate',
    headerWidth: '10rem',
    bodyWidth: '11rem',
  },
  {
    kind: 'deliveryDate',
    headerKey: 'production.lots.columns.stepDeliveryDate',
    headerWidth: '9rem',
    bodyWidth: '9rem',
  },
  {
    kind: 'note',
    headerKey: 'production.lots.columns.stepNote',
    headerWidth: '10rem',
    bodyWidth: '10rem',
  },
]

// Odd-numbered step groups get a slightly darker background so adjacent
// step columns stay visually distinct in Widescreen Mode.
export function stepColumnClass(n: number): string | undefined {
  return n % 2 === 1 ? 'step-col-shade' : undefined
}
