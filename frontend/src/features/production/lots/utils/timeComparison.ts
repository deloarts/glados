import { roundTo, withoutNegativeZero } from '@/core/utils/numbers'

import { stepPerPieceMinutes } from '../../utils/lotStepDisplay'
import type { LotStepResponse } from '../../types/productionLotsResponse'
import type { ManufacturingAssessmentResponse } from '../../types/productionOrdersResponse'

export type TimeComparisonMetric = 'setup' | 'perPiece' | 'total'

// Decimal places of an assessment's minutes per piece, as the backend
// stores them. Sums and differences are rounded to them too, which strips
// the float noise a product of decimals picks up, and every minute value of
// the comparison is shown with them.
const MINUTE_DECIMALS = 2

/** Minutes with up to two decimals, without trailing zeros. */
export function formatDecimalMinutes(value: number): string {
  return String(withoutNegativeZero(roundTo(value, MINUTE_DECIMALS)))
}

export interface TimeComparisonRow {
  metric: TimeComparisonMetric
  estimated: number | null
  actual: number | null
  /** actual - estimated; positive means it took longer than planned. */
  diffMinutes: number | null
  /** diffMinutes as a share of the estimate; null when there's nothing to divide by. */
  diffPercent: number | null
}

/**
 * The step's measured per-piece estimate, or its budget share, as the
 * backend computes it for estimated_duration_minutes.
 */
export function effectivePerPieceMinutes(step: LotStepResponse): number {
  return stepPerPieceMinutes(step) ?? 0
}

function diffRow(
  metric: TimeComparisonMetric,
  estimated: number | null,
  actual: number | null,
): TimeComparisonRow {
  const comparable = estimated !== null && actual !== null
  const diffMinutes = comparable ? roundTo(actual - estimated, MINUTE_DECIMALS) : null
  return {
    metric,
    estimated,
    actual,
    diffMinutes,
    // A 0-minute estimate has no meaningful percentage.
    diffPercent:
      diffMinutes !== null && estimated !== null && estimated > 0
        ? (diffMinutes / estimated) * 100
        : null,
  }
}

/**
 * Planned vs. measured effort for one production order.
 *
 * Estimates are per step and actuals per order, so estimates are summed
 * across the position's steps and scoped to the order's own quantity, which
 * matters when a position is split across machines.
 *
 * Returns null until someone records what the order actually took.
 */
export function buildTimeComparison(input: {
  steps: LotStepResponse[]
  orderQuantity: number
  estimatedDurationMinutes: number
  assessment: ManufacturingAssessmentResponse | null
}): TimeComparisonRow[] | null {
  const { steps, orderQuantity, estimatedDurationMinutes, assessment } = input
  if (!assessment) return null

  const estimatedSetup = steps.reduce((sum, s) => sum + (s.estimated_setup_minutes ?? 0), 0)
  const estimatedPerPiece = steps.reduce((sum, s) => sum + effectivePerPieceMinutes(s), 0)

  const actualSetup = assessment.actual_setup_minutes
  const actualPerPiece = assessment.actual_minutes_per_piece
  const actualTotal = roundTo((actualSetup ?? 0) + orderQuantity * actualPerPiece, MINUTE_DECIMALS)

  return [
    diffRow('setup', estimatedSetup, actualSetup),
    diffRow('perPiece', estimatedPerPiece, actualPerPiece),
    // The backend's figure, so it matches what the scheduler planned against.
    diffRow('total', estimatedDurationMinutes, actualTotal),
  ]
}
