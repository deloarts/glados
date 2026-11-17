/**
 * Nominal size ranges of ISO 286-1. Every range is "over the previous bound,
 * up to and including this bound", so 30 mm belongs to the range 18 to 30 mm.
 */

/** Upper bounds of the ranges the standard tolerance grades (IT) are tabled for. */
export const IT_RANGE_UPPER_BOUNDS = [
  3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500,
  3150,
] as const

/**
 * Upper bounds of the ranges the fundamental deviations are tabled for. Some
 * letters (a, c, r, s and their hole counterparts) change value at the
 * intermediate steps, so the deviation tables use the finer split up to 500 mm.
 */
export const DEVIATION_RANGE_UPPER_BOUNDS = [
  3, 6, 10, 14, 18, 24, 30, 40, 50, 65, 80, 100, 120, 140, 160, 180, 200, 225, 250, 280, 315, 355,
  400, 450, 500,
] as const

/** Largest nominal size any fundamental deviation table covers. */
export const MAX_DEVIATION_SIZE = 500

/** Largest nominal size the standard tolerance grades cover. */
export const MAX_SIZE = 3150

/** Number of main ranges up to 500 mm (up to 3, 3 to 6, ... 400 to 500). */
export const MAIN_RANGE_COUNT = 13

// For each fine deviation range, the index of the main range it sits in.
const FINE_TO_MAIN = [0, 1, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 8, 9, 9, 9, 10, 10, 11, 11, 12, 12]

function rangeIndex(bounds: readonly number[], size: number): number | null {
  if (!Number.isFinite(size) || size <= 0) return null
  const index = bounds.findIndex((upper) => size <= upper)
  return index < 0 ? null : index
}

/** Index into the IT tables, or null when the size is not covered. */
export function itRangeIndex(size: number): number | null {
  return rangeIndex(IT_RANGE_UPPER_BOUNDS, size)
}

/** Index into the fine deviation tables, or null above 500 mm or for a non-positive size. */
export function deviationRangeIndex(size: number): number | null {
  return rangeIndex(DEVIATION_RANGE_UPPER_BOUNDS, size)
}

/** Index of the main range up to 500 mm, or null outside it. */
export function mainRangeIndex(size: number): number | null {
  const fine = deviationRangeIndex(size)
  return fine === null ? null : (FINE_TO_MAIN[fine] ?? null)
}

/**
 * Expands a row given per main range (13 values) to one value per fine
 * deviation range (25 values), for letters whose value does not change at the
 * intermediate steps.
 */
export function byMainRange<T>(values: readonly T[]): T[] {
  if (values.length !== MAIN_RANGE_COUNT) {
    throw new Error(`Expected ${MAIN_RANGE_COUNT} main range values, got ${values.length}`)
  }
  return FINE_TO_MAIN.map((main) => values[main] as T)
}
