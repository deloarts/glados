import type {
  SequenceAction,
  SequenceConditionTerm,
  SequenceStep,
  SequenceTransition,
  SequenceVariantValue,
} from '../types/sequence'
import { TARGET_NEXT } from '../types/sequence'

/**
 * The steps of a sequence in one canonical shape: every field present, in
 * the order the server sends them, so that comparing two versions as JSON
 * tells whether anything changed.
 */

function value(raw: SequenceVariantValue | null | undefined): SequenceVariantValue | null {
  if (!raw) return null
  const perVariant = Object.fromEntries(
    Object.entries(raw.per_variant ?? {}).sort(([a], [b]) => Number(a) - Number(b)),
  )
  return { common: raw.common ?? null, per_variant: perVariant }
}

function term(raw: SequenceConditionTerm): SequenceConditionTerm {
  return {
    kind: raw.kind,
    device_id: raw.device_id ?? null,
    position_id: raw.position_id ?? null,
    comparator: raw.comparator ?? null,
    value: value(raw.value),
    step_key: raw.step_key ?? null,
    duration_ms: value(raw.duration_ms),
    text: raw.text ?? null,
  }
}

function action(raw: SequenceAction): SequenceAction {
  return {
    key: raw.key,
    kind: raw.kind,
    qualifier: raw.qualifier ?? 'stored',
    device_id: raw.device_id ?? null,
    position_id: raw.position_id ?? null,
    value: value(raw.value),
    text: raw.text ?? null,
    description: raw.description ?? null,
    condition: (raw.condition ?? []).map(term),
    duration_ms: value(raw.duration_ms),
  }
}

function transition(raw: SequenceTransition): SequenceTransition {
  return { key: raw.key, target: raw.target ?? TARGET_NEXT, condition: (raw.condition ?? []).map(term) }
}

export function normalizeSteps(raw: readonly SequenceStep[]): SequenceStep[] {
  return raw.map((step) => ({
    key: step.key,
    description: step.description ?? null,
    timeout_ms: step.timeout_ms ?? null,
    expected_duration_ms: value(step.expected_duration_ms),
    actions: (step.actions ?? []).map(action),
    transitions: (step.transitions ?? []).map(transition),
  }))
}

export function sameSteps(a: readonly SequenceStep[], b: readonly SequenceStep[]): boolean {
  return JSON.stringify(normalizeSteps(a)) === JSON.stringify(normalizeSteps(b))
}

/** A fresh key for a step, action or transition, unique within the sequence. */
export function newKey(prefix: 's' | 'a' | 't'): string {
  const random = Math.random().toString(36).slice(2, 10)
  return `${prefix}${Date.now().toString(36)}${random}`
}
