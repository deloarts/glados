import { updatePrimaryPalette, updateSurfacePalette, usePreset } from '@openvue/themes'
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { PRIMARY_COLORS, SURFACES } from '@/core/config/colorPalettes'
import { themePresets } from '@/core/config/themePresets'
import { safeStorage } from '@/core/utils/safeStorage'

interface AppState {
  primary: string
  surface: string | null
  darkMode: boolean
  sidebarWide: boolean
  buttonFlatStyle: boolean
  tableGridlines: boolean
  tableStriped: boolean
}

/**
 * The OS preference. Exported so a caller dropping a temporary dark-mode
 * override (aperture mode) has somewhere to fall back to when the user has no
 * saved choice of their own: the same thing initDefaultTheme boots with.
 */
export function prefersDarkMode(): boolean {
  return typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-color-scheme: dark)').matches
    : false
}

const SIDEBAR_WIDE_STORAGE_KEY = 'sidebarWide'

function readStoredSidebarWide(): boolean {
  return safeStorage.get(SIDEBAR_WIDE_STORAGE_KEY) === 'true'
}

export const useLayoutStore = defineStore('layout', () => {
  const appState = ref<AppState>({
    primary: 'glados',
    surface: 'glados',
    darkMode: prefersDarkMode(),
    sidebarWide: readStoredSidebarWide(),
    buttonFlatStyle: false,
    tableGridlines: false,
    tableStriped: false,
  })

  const primaryColors = ref(PRIMARY_COLORS)
  const surfaces = ref(SURFACES)

  // Set once the user's saved theme is applied, so the boot default can
  // never overwrite it, whichever finishes first on startup.
  let hasUserTheme = false

  // Kept so the OS listener can be removed once a real preference is known,
  // or OS changes would flip the user's choice.
  let darkModeMediaQuery: MediaQueryList | null = null
  let darkModeListener: ((e: MediaQueryListEvent) => void) | null = null

  function stopFollowingOsDarkMode(): void {
    if (darkModeMediaQuery && darkModeListener) {
      darkModeMediaQuery.removeEventListener('change', darkModeListener)
    }
    darkModeMediaQuery = null
    darkModeListener = null
  }

  function setPrimary(value: string) {
    appState.value.primary = value
  }

  function setSurface(value: string | null) {
    appState.value.surface = value
  }

  /**
   * Boot-time placeholder: OS dark-mode preference + the default primary
   * palette, live-updating with the OS until a signed-in user's own theme
   * (applyUserTheme) is known, at which point it stops applying and its OS
   * listener is torn down. A no-op if the user's theme already arrived first.
   */
  function initDefaultTheme() {
    if (hasUserTheme) return
    updateColors('primary', 'glados')

    if (typeof window.matchMedia !== 'function') return
    darkModeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    setDarkMode(darkModeMediaQuery.matches)
    darkModeListener = (e) => {
      if (hasUserTheme) return
      setDarkMode(e.matches)
    }
    darkModeMediaQuery.addEventListener('change', darkModeListener)
  }

  function setDarkMode(value: boolean) {
    appState.value.darkMode = value
    document.documentElement.classList.toggle('p-dark', value)
  }

  function toggleDarkMode() {
    const value = !appState.value.darkMode
    setDarkMode(value)
    return value
  }

  function toggleSidebarWide() {
    const value = !appState.value.sidebarWide
    appState.value.sidebarWide = value
    safeStorage.set(SIDEBAR_WIDE_STORAGE_KEY, String(value))
    return value
  }

  function updateColors(type: string, colorName: string) {
    if (type === 'primary') {
      setPrimary(colorName)
      const color = primaryColors.value.find((c) => c.name === colorName)
      if (color) updatePrimaryPalette(color.palette)
    } else if (type === 'surface') {
      setSurface(colorName)
      const surfaceColor = surfaces.value.find((s) => s.name === colorName)
      if (surfaceColor) updateSurfacePalette(surfaceColor.palette)
    }
  }

  function setPreset(name: string) {
    const preset = themePresets[name]
    if (preset) usePreset(preset)
  }

  /**
   * Apply a primary palette *without* recording it as the selection.
   *
   * updateColors() does both, which is right when the user picked the colour
   * and wrong when something is temporarily painting over their choice: the
   * choice has to survive, or there is nothing to go back to.
   */
  function paintPrimary(colorName: string) {
    const color = primaryColors.value.find((c) => c.name === colorName)
    if (color) updatePrimaryPalette(color.palette)
  }

  /**
   * Swap the preset without losing the user's colours.
   *
   * usePreset() replaces the entire theme, palettes included, so a bare
   * setPreset() silently reverts primary and surface to whatever that preset
   * ships with (OpenVue's stock green, in most cases). applyUserTheme does
   * these same two steps in this same order for exactly that reason; anything
   * changing the preset on its own needs to as well.
   *
   * `primaryOverride` paints a different primary on top, leaving the user's
   * own selection recorded so a later call without the override restores it.
   */
  function applyPreset(name: string, primaryOverride?: string) {
    setPreset(name)
    if (primaryOverride) paintPrimary(primaryOverride)
    else updateColors('primary', appState.value.primary)
    if (appState.value.surface) updateColors('surface', appState.value.surface)
  }

  function applyUserTheme(
    preset: string | null,
    primary: string | null,
    surface: string | null,
    darkMode: boolean,
  ) {
    // From here on the user's own preference is authoritative: the boot
    // default no longer applies even if it hasn't run yet, and the OS can
    // no longer flip it out from under them.
    hasUserTheme = true
    stopFollowingOsDarkMode()

    if (preset) setPreset(preset)
    if (primary) updateColors('primary', primary)
    if (surface) updateColors('surface', surface)
    setDarkMode(darkMode)
  }

  function applyVisualAids(
    buttonFlatStyle: boolean,
    tableGridlines: boolean,
    tableStriped: boolean,
  ) {
    appState.value.buttonFlatStyle = buttonFlatStyle
    appState.value.tableGridlines = tableGridlines
    appState.value.tableStriped = tableStriped
  }

  const isDarkMode = computed(() => appState.value.darkMode)
  const primary = computed(() => appState.value.primary)
  const surface = computed(() => appState.value.surface)
  const isSidebarWide = computed(() => appState.value.sidebarWide)
  const isButtonFlatStyleEnabled = computed(() => appState.value.buttonFlatStyle)
  const isTableGridlinesEnabled = computed(() => appState.value.tableGridlines)
  const isTableStripedEnabled = computed(() => appState.value.tableStriped)

  return {
    primaryColors,
    surfaces,
    isDarkMode,
    primary,
    surface,
    isSidebarWide,
    isButtonFlatStyleEnabled,
    isTableGridlinesEnabled,
    isTableStripedEnabled,
    initDefaultTheme,
    toggleDarkMode,
    toggleSidebarWide,
    setDarkMode,
    setPrimary,
    setSurface,
    updateColors,
    setPreset,
    applyPreset,
    applyUserTheme,
    applyVisualAids,
  }
})
