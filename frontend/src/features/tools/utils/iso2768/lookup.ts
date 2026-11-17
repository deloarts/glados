import type { SizeRange, ToleranceTable } from './tables'

export type LookupFailure = 'invalidSize' | 'belowRange' | 'aboveRange' | 'notDefined'

export type LookupResult =
  | { ok: true; value: number; rangeIndex: number }
  | { ok: false; reason: LookupFailure; rangeIndex: number | null }

function inRange(range: SizeRange, size: number): boolean {
  const aboveFrom = range.includeFrom ? size >= range.from : size > range.from
  return aboveFrom && (range.to === null || size <= range.to)
}

/** Index of the range a size falls in, or null when no range covers it. */
export function rangeIndexOf(ranges: readonly SizeRange[], size: number): number | null {
  const index = ranges.findIndex((range) => inRange(range, size))
  return index < 0 ? null : index
}

/**
 * The tolerance a class gets at a size, or why the table has none: the size is
 * below or above every range, or the class leaves that range undefined.
 */
export function lookup<C extends string>(
  table: ToleranceTable<C>,
  cls: C,
  size: number,
): LookupResult {
  if (!Number.isFinite(size) || size <= 0) return { ok: false, reason: 'invalidSize', rangeIndex: null }
  const rangeIndex = rangeIndexOf(table.ranges, size)
  if (rangeIndex === null) {
    const first = table.ranges[0]
    const below = first !== undefined && size <= first.from
    return { ok: false, reason: below ? 'belowRange' : 'aboveRange', rangeIndex: null }
  }
  const value = table.values[cls][rangeIndex]
  if (value === null || value === undefined) return { ok: false, reason: 'notDefined', rangeIndex }
  return { ok: true, value, rangeIndex }
}

/** Splits minutes of arc into whole degrees and remaining minutes. */
export function degreesAndMinutes(minutes: number): { degrees: number; minutes: number } {
  return { degrees: Math.floor(minutes / 60), minutes: minutes % 60 }
}
