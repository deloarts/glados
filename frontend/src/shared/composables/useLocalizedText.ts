import { useI18n } from 'vue-i18n'

import { useHostStore } from '@/core/host/stores/hostStore'
import { resolveLocalizedText, type LocalizedText } from '@/shared/utils/localizedText'

/**
 * Resolves localized labels against the current UI language, falling back
 * to the instance's default language.
 */
export function useLocalizedText(): {
  localize: (text: LocalizedText | string | null | undefined) => string
} {
  const { locale } = useI18n()
  const host = useHostStore()

  function localize(text: LocalizedText | string | null | undefined): string {
    return resolveLocalizedText(text, locale.value, host.defaultLanguage)
  }

  return { localize }
}
