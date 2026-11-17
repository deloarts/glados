import { formula, span } from '@/shared/reports'
import type { Inline, KeyValue, ReportStyle, ReportTranslate } from '@/shared/reports'
import { formatQuantity, splitSubscripts } from './format'
import type { SafetyDistanceFormat } from './format'
import type { Unit } from './types'

/** Text pieces the Safety Distance report modules share. */

export const P = 'tools.safetyDistance'
export const F = `${P}.fields`
export const RT = `${P}.responseTime`

/** Text in the standard's notation, with its symbols as real subscripts. */
export function rich(text: string, style?: ReportStyle): Inline {
  return formula(splitSubscripts(text), style)
}

/** A label followed by its symbol, "Detection capability d_e". */
export function labelled(label: string, symbol?: string): KeyValue['label'] {
  if (!symbol) return label
  return [`${label} `, rich(symbol, 'symbol')]
}

export function quantity(value: number | null, unit: Unit, f: SafetyDistanceFormat): string {
  return value === null ? '–' : formatQuantity(value, unit, f)
}

export function yesNo(value: boolean, t: ReportTranslate): string {
  return t(value ? 'common.yes' : 'common.no')
}

/** A value set apart from its line, such as a computed result. */
export function strong(text: string): Inline {
  return span(text, 'emphasis')
}
