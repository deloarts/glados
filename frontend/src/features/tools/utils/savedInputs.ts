/**
 * Reading the inputs of a saved calculation back into a tool tab. A saved
 * input map comes from an older version of the tool as often as from the
 * current one, so every part is checked before it is used.
 */

/** The saved part when it is text, else null (missing). */
export function savedString(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

/**
 * A saved nominal size in mm. Missing gives `fallback` silently; text that is
 * not a number in (0, `max`] gives `fallback` flagged as invalid, so the tab
 * can tell the user once. A decimal comma is accepted.
 */
export function parseSavedSize(
  raw: string | null,
  fallback: number,
  max: number,
): { size: number; invalid: boolean } {
  if (raw === null) return { size: fallback, invalid: false }
  const parsed = Number(raw.replace(',', '.'))
  return Number.isFinite(parsed) && parsed > 0 && parsed <= max
    ? { size: parsed, invalid: false }
    : { size: fallback, invalid: true }
}
