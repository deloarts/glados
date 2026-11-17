/**
 * Comparisons behind the saved-calculation status: whether the tool's current
 * inputs are still the saved ones, and whether recalculating them gives the
 * saved results. Numbers count as equal within a tiny relative tolerance, so
 * floating point noise between browsers never reads as a changed result.
 */

import { isPlainRecord } from '@/core/utils/guards'

const RELATIVE_TOLERANCE = 1e-9

function numbersEqual(a: number, b: number): boolean {
  if (a === b) return true
  return Math.abs(a - b) <= RELATIVE_TOLERANCE * Math.max(Math.abs(a), Math.abs(b), 1)
}

export function valuesEqual(a: unknown, b: unknown): boolean {
  if (typeof a === 'number' && typeof b === 'number') return numbersEqual(a, b)
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((item, i) => valuesEqual(item, b[i]))
  }
  if (a && b && typeof a === 'object' && typeof b === 'object') {
    const ra = a as Record<string, unknown>
    const rb = b as Record<string, unknown>
    const keys = new Set([...Object.keys(ra), ...Object.keys(rb)])
    // A key that is undefined on one side and missing on the other is the
    // same thing once serialised to JSON.
    return [...keys].every((key) => valuesEqual(ra[key], rb[key]))
  }
  return a === b || (a === undefined && b === null) || (a === null && b === undefined)
}

export function inputsEqual(a: Record<string, string>, b: Record<string, unknown>): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)])
  return [...keys].every((key) => (a[key] ?? '') === (typeof b[key] === 'string' ? b[key] : ''))
}

export interface ResultDifference {
  path: string
  saved: unknown
  current: unknown
}

/** Leaf values that differ between two results snapshots, by dotted path. */
export function resultDifferences(
  saved: unknown,
  current: unknown,
  path = '',
): ResultDifference[] {
  if (isPlainRecord(saved) && isPlainRecord(current)) {
    const keys = [...new Set([...Object.keys(saved), ...Object.keys(current)])].sort()
    return keys.flatMap((key) =>
      resultDifferences(saved[key], current[key], path ? `${path}.${key}` : key),
    )
  }
  return valuesEqual(saved, current) ? [] : [{ path, saved, current }]
}
