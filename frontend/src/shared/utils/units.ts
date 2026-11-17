import { i18n } from '@/core/i18n'
import type { AppLocale } from '@/core/i18n'

// The unit codes every quantity in the app is stored in. Their labels live
// under boughtItems.units and boughtItems.unitsShort in the locale files.

export const BOUGHT_ITEM_UNIT_CODES = [
  'PCS',
  'UNIT',
  'M',
  'M2',
  'M3',
  'MM',
  'CM',
  'KG',
  'G',
  'T',
  'L',
  'SET',
  'PAIR',
  'H',
  'ROLL',
] as const

export type BoughtItemUnit = (typeof BOUGHT_ITEM_UNIT_CODES)[number]

/** The unit codes that count whole things; a quantity in one of them is a whole number, as the backend checks. */
export const COUNTED_UNIT_CODES: readonly string[] = ['PCS', 'UNIT', 'SET', 'PAIR', 'ROLL']

/** The fraction digits a quantity input in `unit` takes: none for a unit that counts whole things, matched without case and surrounding spaces, three otherwise. */
export function quantityFractionDigits(unit: string | null | undefined): number {
  return COUNTED_UNIT_CODES.includes((unit ?? '').trim().toUpperCase()) ? 0 : 3
}

/** Whether a demand and an order line name different units, compared without case and surrounding spaces, as the backend's unit_mismatch flag does. Nothing converts between units, so the clients warn. */
export function unitsDiffer(demandUnit: string | null | undefined, lineUnit: string | null | undefined): boolean {
  if (!demandUnit || !lineUnit) return false
  return demandUnit.trim().toUpperCase() !== lineUnit.trim().toUpperCase()
}

/** Preselected unit for every form that creates a new quantity: pieces is by far the most common case. */
export const DEFAULT_UNIT: BoughtItemUnit = 'PCS'

/** Locale-aware short label for a stored unit code (e.g. PCS → "pcs", or the German abbreviation in the de-AT locale). The code is matched without case and surrounding spaces, so "pcs" reads as PCS. Unknown values pass through unchanged. Defaults to the UI locale unless an explicit locale is given. */
export function formatUnit(unit: string | null | undefined, locale?: AppLocale): string {
  if (!unit) return ''
  const code = unit.trim().toUpperCase()
  if (!(BOUGHT_ITEM_UNIT_CODES as readonly string[]).includes(code)) return unit
  const key = `boughtItems.unitsShort.${code}`
  return locale ? i18n.global.t(key, {}, { locale }) : i18n.global.t(key)
}
