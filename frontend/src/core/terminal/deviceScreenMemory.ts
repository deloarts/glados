/**
 * What a terminal device remembers about the screen it showed last, so the
 * next boot starts in that screen's look and language instead of the tenant
 * default and the display does not flash a different theme or language
 * before the first feed.
 *
 * The record lives in `localStorage` under one key as a JSON object. Every
 * field is optional and read on its own, and a write merges into what is
 * stored, so fields can be added later without dropping the ones already
 * there. Storage that is blocked, full or holds something unreadable counts
 * as nothing remembered.
 *
 * The theme is painted through the layout store's painting calls, which
 * never record it as a user theme, exactly as the screen itself is shown.
 * The language is set as the UI locale, which also drives the date, weekday
 * and number formats.
 */
import { i18n } from '@/core/i18n'
import type { AppLocale } from '@/core/i18n'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { safeStorage } from '@/core/utils/safeStorage'

import type { InfoscreenFeed } from './terminalApi'

export const DEVICE_SCREEN_MEMORY_KEY = 'glados.terminal.screen'

/** What a null preset or primary colour of a screen stands for: the tenant default. */
export const DEFAULT_THEME_PRESET = 'Aura'
export const DEFAULT_PRIMARY_COLOR = 'glados'

export type ScreenTheme = Pick<
  InfoscreenFeed['infoscreen'],
  'color_mode' | 'theme_preset' | 'primary_color'
>

export interface DeviceScreenMemory {
  /** The theme of the last screen shown, or null when none was shown yet. */
  theme: ScreenTheme | null
  /** The language of the last screen shown, or null when none was shown yet. */
  language: AppLocale | null
}

const SCREEN_LANGUAGES: readonly AppLocale[] = ['enGB', 'deAT']

function readStoredObject(): Record<string, unknown> {
  const raw = safeStorage.get(DEVICE_SCREEN_MEMORY_KEY)
  if (!raw) return {}
  try {
    const parsed: unknown = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {}
  } catch {
    return {}
  }
}

function themeFrom(value: unknown): ScreenTheme | null {
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  const colorMode = record.color_mode
  const preset = record.theme_preset ?? null
  const primary = record.primary_color ?? null
  if (colorMode !== 'dark' && colorMode !== 'light') return null
  if (preset !== null && typeof preset !== 'string') return null
  if (primary !== null && typeof primary !== 'string') return null
  return {
    color_mode: colorMode,
    theme_preset: preset as ScreenTheme['theme_preset'],
    primary_color: primary,
  }
}

function languageFrom(value: unknown): AppLocale | null {
  return SCREEN_LANGUAGES.find((language) => language === value) ?? null
}

/** The remembered record, with every field that is missing or unreadable as null. */
export function readDeviceScreenMemory(): DeviceScreenMemory {
  const stored = readStoredObject()
  return { theme: themeFrom(stored.theme), language: languageFrom(stored.language) }
}

/** Merges the given fields into the remembered record; false when storage refused the write. */
export function updateDeviceScreenMemory(fields: Partial<DeviceScreenMemory>): boolean {
  try {
    return safeStorage.set(
      DEVICE_SCREEN_MEMORY_KEY,
      JSON.stringify({ ...readStoredObject(), ...fields }),
    )
  } catch {
    return false
  }
}

/**
 * Paints a screen's theme without recording it as anybody's own theme. A
 * caller that holds the layout store of its own app passes it in.
 */
export function paintScreenTheme(
  theme: ScreenTheme,
  layoutStore: ReturnType<typeof useLayoutStore> = useLayoutStore(),
): void {
  layoutStore.applyPreset(
    theme.theme_preset ?? DEFAULT_THEME_PRESET,
    theme.primary_color ?? DEFAULT_PRIMARY_COLOR,
  )
  layoutStore.setDarkMode(theme.color_mode !== 'light')
}

/** Paints the remembered theme, if there is one, and tells whether it did. */
export function paintRememberedScreenTheme(): boolean {
  const { theme } = readDeviceScreenMemory()
  if (!theme) return false
  paintScreenTheme(theme)
  return true
}

// The screen language this page shows, so it can be put back after
// something that sets the tenant default for anonymous visitors.
let shownLanguage: AppLocale | null = null

/** Shows the UI in a screen's language. An unknown language is ignored. */
export function paintScreenLanguage(language: string): void {
  const known = languageFrom(language)
  if (!known) return
  shownLanguage = known
  i18n.global.locale.value = known
}

/** Shows the remembered language, if there is one, and tells whether it did. */
export function paintRememberedScreenLanguage(): boolean {
  const { language } = readDeviceScreenMemory()
  if (!language) return false
  paintScreenLanguage(language)
  return true
}

/**
 * Puts the screen language shown last back, after the public branding has
 * set the tenant default. Does nothing before a screen language was shown.
 */
export function repaintScreenLanguage(): void {
  if (shownLanguage) i18n.global.locale.value = shownLanguage
}

/** Forgets the screen language shown, when the page leaves it, and in specs. */
export function forgetShownScreenLanguage(): void {
  shownLanguage = null
}
