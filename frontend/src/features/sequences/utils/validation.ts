import type { SequenceConditionTerm, SequenceStep, SequenceVariantValue } from '../types/sequence'
import { TARGET_END, TARGET_NEXT } from '../types/sequence'

/**
 * The problems of a sequence's steps the editor points out while they are
 * edited, mirroring the server's checks that need no lookup beyond the
 * names on screen, plus warnings the server does not raise: alternative
 * transitions whose conditions are the same, so it is not clear which one
 * is taken, and a transition that waits for a device in another position
 * than the step moves it to, which is usually a condition left behind
 * when the action changed. Each problem is an i18n key under
 * sequences.problems.
 */

export interface StepProblems {
  errors: string[]
  warnings: string[]
}

export interface ProblemContext {
  /** Whether a position takes a value, by device and position id. */
  takesValue: (deviceId: number, positionId: number) => boolean
  liveVariantIds: number[]
  /** Whether a device moves with another one, so a step cannot move it. */
  isDriven: (deviceId: number) => boolean
}

function complete(value: SequenceVariantValue | null | undefined, context: ProblemContext): boolean {
  if (!value) return false
  if (value.common !== null && value.common !== undefined) return true
  const own = value.per_variant ?? {}
  return context.liveVariantIds.length > 0 && context.liveVariantIds.every((id) => own[String(id)] !== undefined)
}

function termProblem(term: SequenceConditionTerm, stepKeys: Set<string>, context: ProblemContext): string | null {
  switch (term.kind) {
    case 'device_position':
      return term.device_id && term.position_id ? null : 'termIncomplete'
    case 'device_value':
      if (!term.device_id || !term.comparator) return 'termIncomplete'
      return complete(term.value, context) ? null : 'valueMissing'
    case 'step_complete':
      return term.step_key && stepKeys.has(term.step_key) ? null : 'termIncomplete'
    case 'time':
      return complete(term.duration_ms, context) ? null : 'valueMissing'
    case 'external':
      return term.text?.trim() ? null : 'termIncomplete'
  }
}

function sameCondition(a: SequenceConditionTerm[], b: SequenceConditionTerm[]): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

export function stepProblems(steps: readonly SequenceStep[], context: ProblemContext): Map<string, StepProblems> {
  const stepKeys = new Set(steps.map((step) => step.key))
  const result = new Map<string, StepProblems>()
  steps.forEach((step, index) => {
    const errors = new Set<string>()
    const warnings = new Set<string>()
    for (const action of step.actions ?? []) {
      if (action.kind === 'device') {
        if (!action.device_id || !action.position_id) errors.add('actionIncomplete')
        else if (context.isDriven(action.device_id)) errors.add('drivenDevice')
        else if (context.takesValue(action.device_id, action.position_id) && !complete(action.value, context)) {
          errors.add('valueMissing')
        }
      } else if (!action.text?.trim()) {
        errors.add('actionIncomplete')
      }
      for (const term of action.condition ?? []) {
        const problem = termProblem(term, stepKeys, context)
        if (problem) errors.add(problem)
      }
    }
    // The position each device is moved to in the step, by device id.
    const targets = new Map<number, number>()
    for (const action of step.actions ?? []) {
      if (action.kind === 'device' && action.qualifier !== 'pulse' && action.device_id && action.position_id) {
        targets.set(action.device_id, action.position_id)
      }
    }
    const transitions = step.transitions ?? []
    if (transitions.length === 0) errors.add('noTransition')
    for (const transition of transitions) {
      const target = transition.target ?? TARGET_NEXT
      if (target === TARGET_NEXT && index === steps.length - 1) errors.add('noNextStep')
      if (target !== TARGET_NEXT && target !== TARGET_END && !stepKeys.has(target)) errors.add('unknownTarget')
      if (transitions.length > 1 && (transition.condition ?? []).length === 0) errors.add('branchWithoutCondition')
      for (const term of transition.condition ?? []) {
        const problem = termProblem(term, stepKeys, context)
        if (problem) errors.add(problem)
        const moved = term.kind === 'device_position' && term.device_id ? targets.get(term.device_id) : undefined
        if (moved !== undefined && term.position_id && term.position_id !== moved) warnings.add('conditionContradicts')
      }
    }
    for (let i = 0; i < transitions.length; i++) {
      for (let j = i + 1; j < transitions.length; j++) {
        const a = transitions[i]!.condition ?? []
        if (a.length > 0 && sameCondition(a, transitions[j]!.condition ?? [])) warnings.add('branchOverlap')
      }
    }
    if (errors.size || warnings.size) result.set(step.key, { errors: [...errors], warnings: [...warnings] })
  })
  return result
}
