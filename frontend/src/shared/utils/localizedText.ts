/**
 * A label kept in several UI languages at once, as the backend stores it:
 * a map from language code (`enGB`, `deAT`) to text. Missing languages are
 * simply absent.
 */
export type LocalizedText = Record<string, string>

/**
 * The text in `language`, else in `defaultLanguage`, else the first
 * language that has one, else an empty string. Mirrors
 * `LocalizedText.resolve` in the backend. A plain string is a label the
 * server already resolved (the pat-shaped responses some web routes share)
 * and comes back as it is.
 */
export function resolveLocalizedText(
  text: LocalizedText | string | null | undefined,
  language: string,
  defaultLanguage: string,
): string {
  if (!text) return ''
  if (typeof text === 'string') return text
  for (const candidate of [language, defaultLanguage]) {
    const value = text[candidate]
    if (value) return value
  }
  return Object.values(text).find((value) => value) ?? ''
}

/**
 * Drops empty and whitespace-only entries and trims the rest, the shape a
 * request should carry.
 */
export function cleanLocalizedText(text: LocalizedText): LocalizedText {
  const cleaned: LocalizedText = {}
  for (const [language, value] of Object.entries(text)) {
    const trimmed = value.trim()
    if (trimmed) cleaned[language] = trimmed
  }
  return cleaned
}
