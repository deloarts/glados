import type { SequenceNames } from '../composables/useSequenceNames'
import type { SequenceAction, SequenceConditionTerm, SequenceVariantValue } from '../types/sequence'

/**
 * Short texts for the parts of a sequence, as the GRAFCET chart writes them:
 * an action as its device and the command that drives to its position, a
 * condition as its terms joined by a middle dot (AND), a device in a
 * position as "device: position", a step as Xn and a
 * time as "500 ms/X2" (t/Xn).
 */

type Translate = (key: string, values?: Record<string, unknown>) => string

export interface DescribeContext {
  names: SequenceNames
  /** The step number by key. */
  stepNumber: (key: string) => number | null
  /** The key of the step the text belongs to, for time terms. */
  stepKey: string
  variantId: number | null
  t: Translate
}

export function formatVariantValue(
  value: SequenceVariantValue | null | undefined,
  unit: string | null,
  variantId: number | null,
  t: Translate,
): string {
  if (!value) return ''
  const own = variantId === null ? undefined : value.per_variant?.[String(variantId)]
  const number = own ?? value.common
  if (number === null || number === undefined) return t('sequences.editor.perVariant')
  return unit ? `${number} ${unit}` : String(number)
}

export function describeTerm(term: SequenceConditionTerm, context: DescribeContext): string {
  const { names, t } = context
  switch (term.kind) {
    case 'device_position':
      return `${names.deviceName(term.device_id)}: ${names.positionName(term.device_id, term.position_id)}`
    case 'device_value': {
      const unit = names.position(term.device_id, term.position_id)?.unit ?? null
      const sign = term.comparator === 'le' ? '≤' : '≥'
      return `${names.deviceName(term.device_id)} ${sign} ${formatVariantValue(term.value, unit, context.variantId, t)}`
    }
    case 'step_complete': {
      const number = term.step_key ? context.stepNumber(term.step_key) : null
      return `X${number ?? '?'}`
    }
    case 'time': {
      const number = context.stepNumber(context.stepKey)
      return `${formatVariantValue(term.duration_ms, 'ms', context.variantId, t)}/X${number ?? '?'}`
    }
    case 'external':
      return term.text ?? ''
  }
}

export function describeCondition(terms: readonly SequenceConditionTerm[], context: DescribeContext): string {
  return terms.map((term) => describeTerm(term, context)).join(' · ')
}

/** A device action as its device and its command with the value; a text action as its text alone. */
export function describeAction(
  action: SequenceAction,
  context: DescribeContext,
): { device: string | null; text: string } {
  if (action.kind === 'text') return { device: null, text: action.text ?? '' }
  const { names } = context
  const position = names.position(action.device_id, action.position_id)
  const value = position?.takesValue ? formatVariantValue(action.value, position.unit, context.variantId, context.t) : ''
  return {
    device: names.deviceName(action.device_id),
    text: [names.actionName(action.device_id, action.position_id), value].filter(Boolean).join(' '),
  }
}
