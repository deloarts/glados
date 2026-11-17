import { i18n } from '@/core/i18n'

/**
 * A `tm()` lookup typed and checked as `string[]`, rather than cast.
 *
 * vue-i18n types `tm()`'s return as `TranslateResult`, effectively `unknown`
 * for a nested array of strings, so a caller that knows its key resolves to
 * a string array today has nothing but `tm(key) as unknown as string[]` to
 * reach for, a cast that stays silently green even if the locale file's
 * shape ever changes under it. This checks the shape at runtime instead:
 * anything other than an array of strings becomes an empty array, the same
 * "nothing to show" fallback callers already use for a missing key.
 *
 * Reads the global i18n instance directly rather than requiring a component
 * setup context, the same choice `localeTag()` makes in core/utils/dates.ts.
 */
export function tmStringArray(key: string): string[] {
  const value: unknown = i18n.global.tm(key)
  return Array.isArray(value) && value.every((entry) => typeof entry === 'string') ? value : []
}
