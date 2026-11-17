import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'
import { resolveLocalizedText, type LocalizedText } from '@/shared/utils/localizedText'

/**
 * A localized label in the current UI language, falling back to the
 * instance's default language, for code outside a component setup (row
 * grouping, display helpers, report builders). Components use
 * useLocalizedText instead.
 */
export function localizeLabel(text: LocalizedText | string | null | undefined): string {
  if (!text || typeof text === 'string') return text ?? ''
  return resolveLocalizedText(text, i18n.global.locale.value, useHostStore().defaultLanguage)
}

/** The option label of a Select over localized catalogue labels. */
export function labelName(option: { name: LocalizedText | string }): string {
  return localizeLabel(option.name)
}
