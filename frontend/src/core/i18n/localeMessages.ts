import enGB from './locales/en-GB'
import deAT from './locales/de-AT'

/**
 * Every bundled locale's messages, keyed by app locale. Most code reads the
 * active locale through vue-i18n; this is for the few lookups that must see
 * every language at once, such as recognising input typed in any supported
 * language.
 */
export const LOCALE_MESSAGES = { enGB, deAT }

export type LocaleMessages = (typeof LOCALE_MESSAGES)[keyof typeof LOCALE_MESSAGES]

/**
 * A locale's own name in its own language, so a speaker finds their language
 * in a picker whatever the UI language is. An unknown code is returned as is.
 */
export function localeEndonym(code: string, withRegion = false): string {
  const messages = (LOCALE_MESSAGES as Record<string, LocaleMessages | undefined>)[code]
  if (!messages) return code
  return withRegion ? messages.localeName.withRegion : messages.localeName.short
}
