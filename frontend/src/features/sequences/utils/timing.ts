import type { SequenceDeviceName } from '../composables/useSequenceNames'
import type { SequenceConditionTerm, SequenceStep, SequenceTransition, SequenceVariantValue } from '../types/sequence'
import { TARGET_END, TARGET_NEXT } from '../types/sequence'

/**
 * The estimated times of a sequence, rough planning data for the cycle
 * time.
 *
 * A step takes as long as the longest of its actions (an action's own time,
 * or else its device's travel time to the target position, after the delay
 * of a time condition it waits for), the time conditions of the transition
 * it leaves through, and its expected duration. A step without an expected
 * duration is unestimated when an action has no time at all or when it
 * waits for an external signal; a pulse has no duration of its own. An
 * unestimated step still adds what is known of it, so a total reads "at
 * least".
 *
 * A pass runs from step 1 until it returns to step 1 or ends. A transition
 * back to a step the pass has already been through is not taken again, so
 * every other loop counts once, and the step leaves through its next
 * alternative instead.
 */

export interface StepEstimate {
  ms: number
  estimated: boolean
}

export interface PassEstimate {
  ms: number
  /** The steps of the pass without a full estimate. */
  unestimated: number
  /** The keys of the steps the pass goes through, in order. */
  stepKeys: string[]
}

export interface CycleEstimate {
  /** The pass along the picked transitions, the first one of a step unless picked otherwise. */
  picked: PassEstimate
  /** The longest pass over all alternatives. */
  worst: PassEstimate
}

/** Step key to the key of the transition the picked pass leaves it through. */
export type TransitionPicks = Record<string, string>

// Enough for any sequence drawn by hand; a pathological branch structure
// stops there instead of freezing the page.
const MAX_VISITS = 20000

const END = -1

export function forVariant(value: SequenceVariantValue | null | undefined, variantId: number | null): number | null {
  if (!value) return null
  if (variantId !== null) {
    const own = value.per_variant?.[String(variantId)]
    if (own !== undefined && own !== null) return own
  }
  return value.common ?? null
}

function waits(condition: readonly SequenceConditionTerm[] | undefined, variantId: number | null) {
  let delay = 0
  let external = false
  for (const term of condition ?? []) {
    if (term.kind === 'time') delay = Math.max(delay, forVariant(term.duration_ms, variantId) ?? 0)
    if (term.kind === 'external') external = true
  }
  return { delay, external }
}

export function estimateStep(
  step: SequenceStep,
  transition: SequenceTransition | undefined,
  devices: ReadonlyMap<number, SequenceDeviceName>,
  variantId: number | null,
): StepEstimate {
  const expected = forVariant(step.expected_duration_ms, variantId)
  let ms = expected ?? 0
  let missing = false
  for (const action of step.actions ?? []) {
    const condition = waits(action.condition, variantId)
    if (condition.external) missing = true
    let own = forVariant(action.duration_ms, variantId)
    if (own === null && action.kind === 'device' && action.device_id != null) {
      const position = devices.get(action.device_id)?.positions.find((p) => p.id === action.position_id)
      own = position?.travelTimeMs ?? null
    }
    if (own === null && action.qualifier === 'pulse') own = 0
    if (own === null) missing = true
    ms = Math.max(ms, condition.delay + (own ?? 0))
  }
  const leaving = waits(transition?.condition, variantId)
  if (leaving.external) missing = true
  ms = Math.max(ms, leaving.delay)
  return { ms, estimated: expected !== null || !missing }
}

function targetIndex(steps: readonly SequenceStep[], index: number, target: string | undefined): number {
  if (target === TARGET_END) return END
  if (!target || target === TARGET_NEXT) return index + 1 < steps.length ? index + 1 : END
  const found = steps.findIndex((step) => step.key === target)
  return found === -1 ? END : found
}

/** The step estimates along the picked transitions, by step key. */
export function estimateSteps(
  steps: readonly SequenceStep[],
  devices: ReadonlyMap<number, SequenceDeviceName>,
  variantId: number | null,
  picks: TransitionPicks = {},
): Map<string, StepEstimate> {
  return new Map(
    steps.map((step) => {
      const transitions = step.transitions ?? []
      const picked = transitions.find((tr) => tr.key === picks[step.key]) ?? transitions[0]
      return [step.key, estimateStep(step, picked, devices, variantId)]
    }),
  )
}

export function estimateCycle(
  steps: readonly SequenceStep[],
  devices: ReadonlyMap<number, SequenceDeviceName>,
  variantId: number | null,
  picks: TransitionPicks = {},
): CycleEstimate | null {
  if (steps.length === 0) return null

  function leave(index: number, transition: SequenceTransition | undefined) {
    const estimate = estimateStep(steps[index] as SequenceStep, transition, devices, variantId)
    return { estimate, next: transition ? targetIndex(steps, index, transition.target) : END }
  }

  // A transition the pass may take: to the end, back to step 1, or to a
  // step it has not been through yet.
  const open = (next: number, visited: ReadonlySet<number>) => next === END || next === 0 || !visited.has(next)

  // The picked pass.
  const picked: PassEstimate = { ms: 0, unestimated: 0, stepKeys: [] }
  const seen = new Set<number>()
  let index = 0
  while (index !== END && !seen.has(index)) {
    seen.add(index)
    const step = steps[index] as SequenceStep
    const transitions = step.transitions ?? []
    const first = transitions.find((tr) => tr.key === picks[step.key]) ?? transitions[0]
    const ordered = first ? [first, ...transitions.filter((tr) => tr !== first)] : []
    const chosen = ordered.find((tr) => open(targetIndex(steps, index, tr.target), seen))
    const { estimate, next } = leave(index, chosen ?? first)
    picked.ms += estimate.ms
    if (!estimate.estimated) picked.unestimated++
    picked.stepKeys.push(step.key)
    index = chosen && next !== 0 ? next : END
  }

  // The worst case, every alternative tried.
  let worst: PassEstimate = picked
  let visits = 0
  function walk(at: number, visited: Set<number>, so: PassEstimate): void {
    if (++visits > MAX_VISITS) return
    const step = steps[at] as SequenceStep
    const transitions = step.transitions ?? []
    const taken = transitions.filter((tr) => open(targetIndex(steps, at, tr.target), visited))
    if (taken.length === 0) {
      finish(at, transitions[0], so)
      return
    }
    for (const transition of taken) {
      const { estimate, next } = leave(at, transition)
      const pass = {
        ms: so.ms + estimate.ms,
        unestimated: so.unestimated + (estimate.estimated ? 0 : 1),
        stepKeys: [...so.stepKeys, step.key],
      }
      if (next === END || next === 0) consider(pass)
      else {
        visited.add(next)
        walk(next, visited, pass)
        visited.delete(next)
      }
    }
  }
  function finish(at: number, transition: SequenceTransition | undefined, so: PassEstimate): void {
    const { estimate } = leave(at, transition)
    consider({
      ms: so.ms + estimate.ms,
      unestimated: so.unestimated + (estimate.estimated ? 0 : 1),
      stepKeys: [...so.stepKeys, (steps[at] as SequenceStep).key],
    })
  }
  function consider(pass: PassEstimate): void {
    if (pass.ms > worst.ms || (pass.ms === worst.ms && pass.unestimated > worst.unestimated)) worst = pass
  }
  walk(0, new Set([0]), { ms: 0, unestimated: 0, stepKeys: [] })

  return { picked, worst }
}

/** A duration as the page shows it: milliseconds below a second, else seconds with one decimal. */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(Math.round(ms / 100) / 10).toFixed(1)} s`
}
