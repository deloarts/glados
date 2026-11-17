import { toWallClockDate } from '@/core/utils/dates'
import type { LotPositionResponse, LotPositionKind } from '../../types/productionLotsResponse'
import type { PlannedStepInfo } from '../components/DeliveryDateCell.vue'

interface PlannedStepCandidate {
  date: Date | null
  startDate: Date | null
  plannedByLabel: string | null
}

export interface ActiveOrderForPlannedInfo {
  id: number
  status: string
}

// eslint-disable-next-line no-restricted-syntax -- a structural constraint the production order response must satisfy
export interface FullOrderForPlannedInfo {
  planned_by: { full_name: string } | null
  planned_end: string | null
  planned_start: string | null
  actual_end: string | null
  actual_start: string | null
}

export interface PlannedStepInfoInput {
  position: Pick<LotPositionResponse, 'expected_delivery_date'> & { kind: LotPositionKind }
  /** The position's one unambiguous active order, or null. */
  activeOrder: ActiveOrderForPlannedInfo | null
  /** activeOrder resolved against the queue store; undefined until loaded. */
  fullOrder: FullOrderForPlannedInfo | undefined
  autoPlannerLabel: string
}

/**
 * Resolves the planned date shown for a lot step's position. A mixed
 * position can have both an external delivery date and internal order
 * dates; the later end and the earlier start are shown.
 */
export function resolvePlannedStepInfo(input: PlannedStepInfoInput): PlannedStepInfo {
  const { position, activeOrder, fullOrder, autoPlannerLabel } = input

  if (position.kind === 'unassigned') return { date: null, startDate: null, plannedByLabel: null }

  const candidates: PlannedStepCandidate[] = []

  if (position.kind === 'external' || position.kind === 'mixed') {
    candidates.push({
      date: position.expected_delivery_date
        ? toWallClockDate(position.expected_delivery_date)
        : null,
      startDate: null,
      // Would need the full order for the orderer's name.
      plannedByLabel: null,
    })
  }

  if ((position.kind === 'internal' || position.kind === 'mixed') && activeOrder) {
    // null planned_by means the scheduler computed the date on its own.
    const plannedByLabel = fullOrder?.planned_by?.full_name ?? autoPlannerLabel
    const source = activeOrder.status === 'completed' ? fullOrder?.actual_end : fullOrder?.planned_end
    const startSource = fullOrder?.actual_start ?? fullOrder?.planned_start
    candidates.push({
      date: source ? toWallClockDate(source) : null,
      startDate: startSource ? toWallClockDate(startSource) : null,
      plannedByLabel,
    })
  }

  const known = candidates.filter((c): c is PlannedStepCandidate & { date: Date } => c.date !== null)
  const knownStarts = candidates.map((c) => c.startDate).filter((d): d is Date => d !== null)
  const startDate =
    knownStarts.length > 0 ? knownStarts.reduce((a, b) => (b.getTime() < a.getTime() ? b : a)) : null

  if (known.length === 0) return { date: null, startDate, plannedByLabel: null }

  const best = known.reduce((a, b) => (b.date.getTime() > a.date.getTime() ? b : a))
  return { date: best.date, startDate, plannedByLabel: best.plannedByLabel }
}
