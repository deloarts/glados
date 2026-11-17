import { roundUp } from './inputs'
import { STANDARDS } from './types'
import type { CalcStep, SafetyMessage, StandardRef, Unit } from './types'

/**
 * Text output of the tool in the user's language. The functions take the
 * translation and number formatting from the caller, so they stay free of
 * Vue and can be used by the tab and its parts alike.
 */
export interface SafetyDistanceFormat {
  t: (key: string, params?: Record<string, unknown>) => string
  /** Formats a number with at most `digits` decimals. */
  number: (value: number, digits: number) => string
}

const PREFIX = 'tools.safetyDistance'

/**
 * Number options of the tool: no digit grouping, as on drawings, so a
 * distance reads 1075 mm in every language and matches the constants in the
 * formulas.
 */
export function numberOptions(digits: number, fixed = false): Intl.NumberFormatOptions {
  return { maximumFractionDigits: digits, minimumFractionDigits: fixed ? digits : 0, useGrouping: false }
}

/** Decimals shown per unit: tenths of a millimetre, tenths of a millisecond. */
const DIGITS: Record<Unit, number> = { mm: 1, s: 4, 'mm/s': 0, '°': 2 }

export function formatQuantity(value: number, unit: Unit, f: SafetyDistanceFormat): string {
  return `${f.number(value, DIGITS[unit])} ${unit}`
}

/** S as the headline shows it: rounded up to 0.1 mm, never shorter than calculated. */
export function formatDistance(value: number, f: SafetyDistanceFormat): string {
  return `${f.number(roundUp(value, 1), 1)} mm`
}

/**
 * Where a value comes from, such as "ISO 13857, 4.2.2, Table 2". `edition`
 * adds the year of the standard, for the headline of the result.
 */
export function formatRef(ref: StandardRef, f: SafetyDistanceFormat, edition = false): string {
  const full = STANDARDS[ref.standard ?? 'iso13855']
  const standard = edition ? full : full.split(':')[0]
  let place = ref.clause
  if (ref.equation) place = f.t(`${PREFIX}.refs.equation`, { clause: ref.clause, n: ref.equation })
  else if (ref.table) place = f.t(`${PREFIX}.refs.table`, { clause: ref.clause, n: ref.table })
  return `${standard}, ${place}`
}

/** The step's expression with its numbers filled in, or null when it has none. */
export function fillExpression(step: CalcStep, f: SafetyDistanceFormat): string | null {
  if (!step.expression) return null
  return step.expression.replace(/\{(\w+)\}/g, (match, name: string) => {
    const value = step.args[name]
    return value === undefined ? match : f.number(value, 4)
  })
}

export function messageText(message: SafetyMessage, f: SafetyDistanceFormat): string {
  const params: Record<string, string> = {}
  for (const [key, value] of Object.entries(message.params ?? {})) params[key] = f.number(value, 4)
  return f.t(`${PREFIX}.messages.${message.code}`, params)
}

export interface TextPart {
  text: string
  sub: boolean
}

const SUBSCRIPT = /([A-Za-zΔ])_(\{[^}]+\}|[A-Za-z0-9/]+)/g

/**
 * Splits text at the standard's symbols so the subscripts can be set apart:
 * "D_DT" gives D and the subscript DT, "H_{D,min}" gives H and "D,min".
 */
export function splitSubscripts(text: string): TextPart[] {
  const result: TextPart[] = []
  let last = 0
  for (const match of text.matchAll(SUBSCRIPT)) {
    const sub = match[2] ?? ''
    result.push({ text: text.slice(last, match.index) + (match[1] ?? ''), sub: false })
    result.push({ text: sub.startsWith('{') ? sub.slice(1, -1) : sub, sub: true })
    last = match.index + match[0].length
  }
  result.push({ text: text.slice(last), sub: false })
  return result.filter((part) => part.text !== '')
}
