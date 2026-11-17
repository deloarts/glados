import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia, storeToRefs } from 'pinia'

import { useLayoutStore } from '../layoutStore'

function stubMatchMedia(initialMatches: boolean) {
  let changeHandler: ((e: { matches: boolean }) => void) | null = null
  const mediaQueryList = {
    matches: initialMatches,
    media: '(prefers-color-scheme: dark)',
    addEventListener: vi.fn<(event: string, handler: (e: { matches: boolean }) => void) => void>(
      (_event, handler) => {
        changeHandler = handler
      },
    ),
    removeEventListener: vi.fn<() => void>(() => {
      changeHandler = null
    }),
  }
  vi.stubGlobal('matchMedia', vi.fn<(query: string) => unknown>().mockReturnValue(mediaQueryList))
  return {
    fireOsChange(matches: boolean) {
      changeHandler?.({ matches })
    },
    removeEventListener: mediaQueryList.removeEventListener,
  }
}

vi.mock('@openvue/themes', () => ({
  // themePresets lays the Glados tokens over each preset at import time.
  definePreset: (preset: unknown) => preset,
  updatePrimaryPalette: vi.fn<() => void>(),
  updateSurfacePalette: vi.fn<() => void>(),
  usePreset: vi.fn<() => void>(),
}))

// The store settles the boot-time theme: App.vue's default (OS dark mode + a
// live matchMedia listener) must never race currentUserStore.refresh()'s
// applyUserTheme, or a slow /users/me would let the OS silently override a
// signed-in user's saved preference, and the listener left behind would keep
// doing so on every later OS flip.
//
// A fresh Pinia instance per test isolates the store's internal state
// (appState, hasUserTheme, the matchMedia listener). useLayoutStore() re-runs
// its whole setup function against the new instance, so no vi.resetModules()
// is needed.
describe('useLayoutStore, theme boot race', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    setActivePinia(createPinia())
  })

  it('applies the OS preference when no user theme has arrived', () => {
    stubMatchMedia(true)
    const layout = useLayoutStore()

    layout.initDefaultTheme()

    expect(layout.isDarkMode).toBe(true)
  })

  it('a later user preference overrides the OS default', () => {
    stubMatchMedia(true)
    const layout = useLayoutStore()

    layout.initDefaultTheme()
    expect(layout.isDarkMode).toBe(true)

    layout.applyUserTheme(null, null, null, false)

    expect(layout.isDarkMode).toBe(false)
  })

  it('an earlier user preference is not clobbered by a late-arriving default', () => {
    stubMatchMedia(true)
    const layout = useLayoutStore()

    // refresh() resolved before App.vue's onMounted this time.
    layout.applyUserTheme(null, null, null, false)
    expect(layout.isDarkMode).toBe(false)

    layout.initDefaultTheme()

    expect(layout.isDarkMode).toBe(false)
  })

  it('stops following the OS once a user preference is applied', () => {
    const media = stubMatchMedia(false)
    const layout = useLayoutStore()

    layout.initDefaultTheme()
    layout.applyUserTheme(null, null, null, true)
    expect(layout.isDarkMode).toBe(true)

    // The OS flipping afterward must not silently override the user's choice.
    media.fireOsChange(false)

    expect(layout.isDarkMode).toBe(true)
    expect(media.removeEventListener).toHaveBeenCalled()
  })

  it('still follows the OS live when no user theme is set', () => {
    const media = stubMatchMedia(false)
    const layout = useLayoutStore()

    layout.initDefaultTheme()
    expect(layout.isDarkMode).toBe(false)

    media.fireOsChange(true)

    expect(layout.isDarkMode).toBe(true)
  })
})

// Every call site destructures the layout store through storeToRefs()
// rather than destructuring the store directly. Plain destructuring off a
// Pinia store copies out the current value and silently freezes it, since
// Pinia's reactive-proxy wrapping auto-unwraps refs on property access. This
// is the single assumption every call site depends on, proven directly
// here rather than only inferred from the type-checker (which can't catch
// a frozen-value bug) and other component tests (which may not happen to
// exercise this specific path).
describe('useLayoutStore, storeToRefs destructuring stays reactive', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('a storeToRefs-destructured ref reflects a later mutation', () => {
    const { isTableGridlinesEnabled } = storeToRefs(useLayoutStore())
    expect(isTableGridlinesEnabled.value).toBe(false)

    useLayoutStore().applyVisualAids(false, true, false)

    expect(isTableGridlinesEnabled.value).toBe(true)
  })

  it('contrast: plain destructuring off the store does NOT stay reactive', () => {
    const { isTableGridlinesEnabled } = useLayoutStore()
    expect(isTableGridlinesEnabled).toBe(false)

    useLayoutStore().applyVisualAids(false, true, false)

    // Frozen at the value it had when destructured. This is exactly the
    // trap storeToRefs() exists to avoid, and why every call site uses it.
    expect(isTableGridlinesEnabled).toBe(false)
  })
})

// usePreset() replaces the whole theme, palettes included. A bare setPreset()
// therefore drops the user's colours back to whatever that preset ships with,
// which showed up as "the theme went green even though glados is selected"
// after the aperture-mode preset swap started calling it.
describe('useLayoutStore, applyPreset keeps the selected colours', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    const themes = await import('@openvue/themes')
    vi.mocked(themes.usePreset).mockClear()
    vi.mocked(themes.updatePrimaryPalette).mockClear()
    vi.mocked(themes.updateSurfacePalette).mockClear()
  })

  it('re-applies primary and surface after swapping the preset', async () => {
    const themes = await import('@openvue/themes')
    const store = useLayoutStore()
    store.updateColors('primary', 'glados')
    store.updateColors('surface', 'glados')
    vi.mocked(themes.updatePrimaryPalette).mockClear()
    vi.mocked(themes.updateSurfacePalette).mockClear()

    store.applyPreset('Nora')

    expect(themes.usePreset).toHaveBeenCalledTimes(1)
    expect(themes.updatePrimaryPalette).toHaveBeenCalledTimes(1)
    expect(themes.updateSurfacePalette).toHaveBeenCalledTimes(1)
    expect(store.primary).toBe('glados')
    expect(store.surface).toBe('glados')
  })

  it('contrast: setPreset alone re-applies nothing', async () => {
    const themes = await import('@openvue/themes')
    const store = useLayoutStore()
    store.updateColors('primary', 'glados')
    vi.mocked(themes.updatePrimaryPalette).mockClear()

    store.setPreset('Nora')

    expect(themes.updatePrimaryPalette).not.toHaveBeenCalled()
  })
})

// Aperture mode paints a reserved red over whatever the user picked. The point
// of "paint" rather than "select" is that their own choice stays recorded, so
// switching the mode off has something to go back to.
describe('useLayoutStore, applyPreset primary override', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    const themes = await import('@openvue/themes')
    vi.mocked(themes.usePreset).mockClear()
    vi.mocked(themes.updatePrimaryPalette).mockClear()
  })

  it('paints the override without overwriting the recorded selection', async () => {
    const themes = await import('@openvue/themes')
    const store = useLayoutStore()
    store.updateColors('primary', 'glados')

    store.applyPreset('Nora', 'aperture')

    const calls = vi.mocked(themes.updatePrimaryPalette).mock.calls
    const painted = calls[calls.length - 1]?.[0]
    expect(painted).toMatchObject({ 500: '#dc2626' })
    // The user's own choice is untouched underneath.
    expect(store.primary).toBe('glados')
  })

  it('restores the recorded selection when the override is dropped', async () => {
    const themes = await import('@openvue/themes')
    const store = useLayoutStore()
    store.updateColors('primary', 'glados')

    store.applyPreset('Nora', 'aperture')
    store.applyPreset('Aura')

    const calls = vi.mocked(themes.updatePrimaryPalette).mock.calls
    const painted = calls[calls.length - 1]?.[0]
    expect(painted).toMatchObject({ 500: '#007acc' })
    expect(store.primary).toBe('glados')
  })

  it('ignores an override naming a palette that does not exist', async () => {
    const themes = await import('@openvue/themes')
    const store = useLayoutStore()
    store.updateColors('primary', 'glados')
    vi.mocked(themes.updatePrimaryPalette).mockClear()

    store.applyPreset('Nora', 'no-such-colour')

    expect(themes.updatePrimaryPalette).not.toHaveBeenCalled()
    expect(store.primary).toBe('glados')
  })
})
