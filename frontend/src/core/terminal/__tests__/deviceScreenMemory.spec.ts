import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'

import { i18n } from '@/core/i18n'

import {
  DEVICE_SCREEN_MEMORY_KEY,
  forgetShownScreenLanguage,
  paintRememberedScreenLanguage,
  paintRememberedScreenTheme,
  repaintScreenLanguage,
  readDeviceScreenMemory,
  updateDeviceScreenMemory,
} from '../deviceScreenMemory'

describe('deviceScreenMemory', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    document.documentElement.classList.remove('p-dark')
  })

  afterEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('p-dark')
    forgetShownScreenLanguage()
    i18n.global.locale.value = 'enGB'
  })

  it('remembers a screen theme and reads it back', () => {
    const theme = { color_mode: 'light', theme_preset: 'Nora', primary_color: 'emerald' } as const

    expect(updateDeviceScreenMemory({ theme })).toBe(true)

    expect(readDeviceScreenMemory()).toEqual({ theme, language: null })
  })

  it('keeps fields it does not know when the theme is written', () => {
    localStorage.setItem(DEVICE_SCREEN_MEMORY_KEY, JSON.stringify({ language: 'deAT' }))

    updateDeviceScreenMemory({
      theme: { color_mode: 'dark', theme_preset: null, primary_color: null },
    })

    expect(JSON.parse(localStorage.getItem(DEVICE_SCREEN_MEMORY_KEY)!)).toEqual({
      language: 'deAT',
      theme: { color_mode: 'dark', theme_preset: null, primary_color: null },
    })
  })

  it('reads nothing from a missing, unreadable or malformed record', () => {
    expect(readDeviceScreenMemory()).toEqual({ theme: null, language: null })

    localStorage.setItem(DEVICE_SCREEN_MEMORY_KEY, '{not json')
    expect(readDeviceScreenMemory()).toEqual({ theme: null, language: null })

    localStorage.setItem(
      DEVICE_SCREEN_MEMORY_KEY,
      JSON.stringify({ theme: { color_mode: 'pink' }, language: 'klingon' }),
    )
    expect(readDeviceScreenMemory()).toEqual({ theme: null, language: null })
  })

  it('treats blocked storage as nothing remembered', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(readDeviceScreenMemory()).toEqual({ theme: null, language: null })
    expect(
      updateDeviceScreenMemory({ theme: { color_mode: 'dark', theme_preset: null, primary_color: null } }),
    ).toBe(false)
    expect(paintRememberedScreenTheme()).toBe(false)
    expect(paintRememberedScreenLanguage()).toBe(false)
  })

  it('paints the remembered theme without recording it as a user theme', () => {
    updateDeviceScreenMemory({
      theme: { color_mode: 'dark', theme_preset: 'Nora', primary_color: 'emerald' },
    })
    const layoutStore = useLayoutStore()
    const applyPreset = vi.spyOn(layoutStore, 'applyPreset')
    const applyUserTheme = vi.spyOn(layoutStore, 'applyUserTheme')

    expect(paintRememberedScreenTheme()).toBe(true)

    expect(applyPreset).toHaveBeenCalledWith('Nora', 'emerald')
    expect(applyUserTheme).not.toHaveBeenCalled()
    expect(document.documentElement.classList.contains('p-dark')).toBe(true)
  })

  it('paints the tenant default for a screen without its own preset and colour', () => {
    updateDeviceScreenMemory({
      theme: { color_mode: 'light', theme_preset: null, primary_color: null },
    })
    const applyPreset = vi.spyOn(useLayoutStore(), 'applyPreset')

    paintRememberedScreenTheme()

    expect(applyPreset).toHaveBeenCalledWith('Aura', 'glados')
    expect(document.documentElement.classList.contains('p-dark')).toBe(false)
  })

  it('paints nothing when no theme is remembered', () => {
    const applyPreset = vi.spyOn(useLayoutStore(), 'applyPreset')

    expect(paintRememberedScreenTheme()).toBe(false)
    expect(applyPreset).not.toHaveBeenCalled()
  })

  it('remembers the language next to the theme', () => {
    const theme = { color_mode: 'dark', theme_preset: null, primary_color: null } as const
    updateDeviceScreenMemory({ theme })

    updateDeviceScreenMemory({ language: 'deAT' })

    expect(readDeviceScreenMemory()).toEqual({ theme, language: 'deAT' })
  })

  it('shows the remembered language as the UI locale', () => {
    updateDeviceScreenMemory({ language: 'deAT' })

    expect(paintRememberedScreenLanguage()).toBe(true)

    expect(i18n.global.locale.value).toBe('deAT')
  })

  it('shows nothing when no language is remembered', () => {
    expect(paintRememberedScreenLanguage()).toBe(false)
    expect(i18n.global.locale.value).toBe('enGB')
  })

  it('puts the shown screen language back after the tenant default replaced it', () => {
    repaintScreenLanguage()
    expect(i18n.global.locale.value).toBe('enGB')

    updateDeviceScreenMemory({ language: 'deAT' })
    paintRememberedScreenLanguage()
    i18n.global.locale.value = 'enGB'

    repaintScreenLanguage()

    expect(i18n.global.locale.value).toBe('deAT')
  })
})
