import {
  formatMinutesDuration,
  methodTooltipSuffix,
  sortedSteps,
  stepLabel,
  stepMethodLabel,
  stepPerPieceMinutes,
  type Translate,
} from '../../utils/lotStepDisplay'

import type {
  LotSummaryPositionResponse,
  LotSummaryResponse,
  LotSummaryStepResponse,
} from '../../types/productionLotsResponse'

// A lot position seen from the lots table: steps sharing a position_id.
// The position, not the step, is what gets assigned to an order, machine
// or manual workplace.
export interface LotStepGroup {
  positionId: number
  steps: LotSummaryStepResponse[]
  primary: LotSummaryStepResponse
}

export function positionGroups(lot: LotSummaryResponse): LotStepGroup[] {
  const steps = sortedSteps(lot)
  const order: number[] = []
  const byPosition = new Map<number, LotSummaryStepResponse[]>()
  for (const step of steps) {
    if (!byPosition.has(step.position_id)) {
      byPosition.set(step.position_id, [])
      order.push(step.position_id)
    }
    byPosition.get(step.position_id)!.push(step)
  }
  return order.map((positionId) => {
    const groupSteps = byPosition.get(positionId)!
    return { positionId, steps: groupSteps, primary: groupSteps[0]! }
  })
}

// Maps the app locale code to a BCP-47 tag for Intl.
function bcp47LocaleTag(locale: string): string {
  return locale === 'deAT' ? 'de-AT' : 'en-GB'
}

// Multi-step groups join their method labels with a localized conjunction
// and append the allocated-fraction suffix.
export function groupMethodLabel(
  group: LotStepGroup,
  locale: string,
): string {
  if (group.steps.length === 1) return stepLabel(group.primary)
  const joined = new Intl.ListFormat(bcp47LocaleTag(locale), { type: 'conjunction' }).format(
    group.steps.map((s) => stepMethodLabel(s)),
  )
  const { position_quantity, position_quantity_remaining } = group.primary
  const allocated = position_quantity - position_quantity_remaining
  if (allocated <= 0 || allocated >= position_quantity) return joined
  return `${joined} (${allocated}/${position_quantity})`
}

// null only when no step has a setup time.
export function groupSetupMinutes(group: LotStepGroup): number | null {
  if (group.steps.every((s) => s.estimated_setup_minutes == null)) return null
  return group.steps.reduce((sum, s) => sum + (s.estimated_setup_minutes ?? 0), 0)
}

export interface GroupPerPiece {
  minutes: number
  // At least one step fell back to its estimated time budget.
  estimated: boolean
}

export function groupPerPiece(group: LotStepGroup): GroupPerPiece | null {
  let minutes = 0
  let estimated = false
  let any = false
  for (const step of group.steps) {
    if (step.estimated_minutes_per_piece != null) {
      minutes += step.estimated_minutes_per_piece
      any = true
    } else if (step.time_budget_per_piece != null) {
      minutes += step.time_budget_per_piece
      estimated = true
      any = true
    }
  }
  return any ? { minutes, estimated } : null
}

export function groupTotalMinutes(group: LotStepGroup): number | null {
  const perPiece = groupPerPiece(group)
  if (perPiece === null) return null
  const setup = groupSetupMinutes(group) ?? 0
  return setup + group.primary.position_quantity * perPiece.minutes
}

export function groupNoteLine(group: LotStepGroup): string | null {
  const notes = group.steps.map((s) => s.note).filter((n): n is string => !!n)
  return notes.length > 0 ? notes.join(' · ') : null
}

// One line per step, empty for a single-step group.
function stepBreakdown(group: LotStepGroup): string | undefined {
  if (group.steps.length <= 1) return undefined
  return group.steps
    .map((step) => {
      const perPiece = stepPerPieceMinutes(step)
      const timing = [
        step.estimated_setup_minutes != null
          ? formatMinutesDuration(step.estimated_setup_minutes)
          : null,
        perPiece != null ? formatMinutesDuration(perPiece) : null,
      ]
        .filter((part): part is string => part !== null)
        .join(' + ')
      const label = stepMethodLabel(step)
      return timing ? `${label}, ${timing}` : label
    })
    .join('\n')
}

// The method cell tooltip: the per-step breakdown plus, when position and t
// are passed, who fulfils the position.
export function groupBreakdownTooltip(
  group: LotStepGroup,
  position?: LotSummaryPositionResponse,
  t?: Translate,
): string | undefined {
  const breakdown = stepBreakdown(group)
  const suffix = position && t ? methodTooltipSuffix(position, t) : undefined
  const parts = [breakdown, suffix].filter((part): part is string => !!part)
  return parts.length > 0 ? parts.join('\n') : undefined
}
