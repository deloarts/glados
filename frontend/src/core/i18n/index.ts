import { watch } from 'vue'
import { createI18n } from 'vue-i18n'

import enGB from './locales/en-GB'
import deAT from './locales/de-AT'
import { localeTag } from '@/core/utils/dates'

export const i18n = createI18n({
  legacy: false,
  locale: 'enGB',
  fallbackLocale: 'enGB',

  messages: {
    enGB,
    deAT,
  },
})

export type AppLocale = 'enGB' | 'deAT'

/**
 * Translates a key, the shape of vue-i18n's `t` that plain helpers take so
 * that test stubs satisfy it too.
 */
export type Translate = (key: string, params?: Record<string, unknown>) => string

// Keeps <html lang> aligned with the active UI language, screen readers and
// the browser's own language-dependent behaviour (spellcheck, translation
// prompts) key off this attribute, not vue-i18n's own state.
watch(
  i18n.global.locale,
  (locale) => {
    document.documentElement.lang = localeTag(locale as AppLocale)
  },
  { immediate: true },
)

/** Maps an ISO 639-1 language code (e.g. a supplier's order_language) to an app locale. Unset or unsupported languages fall back to English. */
export function appLocaleForLanguage(code: string | null | undefined): AppLocale {
  return code?.toLowerCase() === 'de' ? 'deAT' : 'enGB'
}
