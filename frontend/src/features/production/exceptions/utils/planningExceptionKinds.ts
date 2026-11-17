import type { PlanningExceptionKind } from '../types/planningExceptionResponse'

/** Every kind in the order the list sorts its rows. */
export const PLANNING_EXCEPTION_KINDS: PlanningExceptionKind[] = [
  'lost_at_receipt',
  'closed_short',
  'lot_ended_short',
  'material_short',
  'late',
]

/** The tag colour of each kind, the same in the table and the info bar. */
export const PLANNING_EXCEPTION_SEVERITY: Record<PlanningExceptionKind, 'danger' | 'warn' | 'info'> = {
  lost_at_receipt: 'danger',
  closed_short: 'warn',
  lot_ended_short: 'danger',
  material_short: 'warn',
  late: 'info',
}
