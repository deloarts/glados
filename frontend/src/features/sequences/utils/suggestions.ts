import type { SequenceConditionTerm, SequenceStep } from '../types/sequence'
import { newTerm } from './factories'

/**
 * The conditions a transition of a step is offered with one click: each
 * device the step moves in its target position, the usual way to wait for
 * a move to finish. A pulse only starts something, so it is left out, as
 * are terms the condition already holds.
 */
export function arrivalSuggestions(
  step: SequenceStep,
  condition: readonly SequenceConditionTerm[],
): SequenceConditionTerm[] {
  const result: SequenceConditionTerm[] = []
  const seen = new Set(
    condition.filter((term) => term.kind === 'device_position').map((term) => `${term.device_id}:${term.position_id}`),
  )
  for (const action of step.actions ?? []) {
    if (action.kind !== 'device' || action.qualifier === 'pulse') continue
    if (action.device_id == null || action.position_id == null) continue
    const key = `${action.device_id}:${action.position_id}`
    if (seen.has(key)) continue
    seen.add(key)
    result.push({ ...newTerm('device_position'), device_id: action.device_id, position_id: action.position_id })
  }
  return result
}
