import { getEmptyPlaceholder } from './emptyValue'

/**
 * Renders a number with at most one decimal place, dropping a trailing
 * ".0" so whole values stay whole (5 → "5", not "5.0").
 *
 * Quantities, masses and minute figures all arrive from the backend as
 * floats, so without this a value that is conceptually "4" can render as
 * 4.000000000000001, and an apportioned per-piece estimate as
 * 2.3333333333333335.
 *
 * Deliberately not locale-aware: the rest of the app renders numbers with a
 * plain decimal point, and switching separators in one dialog only would
 * read as a bug rather than a fix.
 */
export function formatDecimal(value: number | null | undefined, fallback?: string): string {
  const empty = fallback ?? getEmptyPlaceholder()
  if (value === null || value === undefined || Number.isNaN(value)) return empty
  if (!Number.isFinite(value)) return empty
  return String(Math.round(value * 10) / 10)
}

/**
 * `value` rounded to `digits` decimals the way `toFixed` rounds, as a number.
 * It strips the float noise a running sum picks up (0.1 + 0.2 becomes 0.3).
 * A tiny negative value comes back as -0, so a caller that renders the result
 * passes it through `withoutNegativeZero`.
 */
export function roundTo(value: number, digits: number): number {
  return Number(value.toFixed(digits))
}

/** `value` with a negative zero turned into 0, so it never renders as "-0". */
export function withoutNegativeZero(value: number): number {
  return value === 0 ? 0 : value
}
