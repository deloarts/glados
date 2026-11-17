/**
 * Narrowing helpers for JSON of unknown shape, such as a results snapshot
 * saved by an older version of a tool.
 */

/** True for a JSON object, not null and not an array. */
export function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** The value when it is a JSON object, else null. */
export function plainRecordOrNull(value: unknown): Record<string, unknown> | null {
  return isPlainRecord(value) ? value : null
}

/** The value when it is a finite number, else null. */
export function finiteNumberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}
