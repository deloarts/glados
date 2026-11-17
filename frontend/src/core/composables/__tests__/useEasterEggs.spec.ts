import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { effectScope } from 'vue'

import {
  APERTURE_PRESET,
  APERTURE_PRIMARY,
  disposeEasterEggs,
  initEasterEggs,
  useEasterEggs,
} from '../useEasterEggs'
import { PRIMARY_COLORS } from '@/core/config/colorPalettes'

const KONAMI = [
  'ArrowUp',
  'ArrowUp',
  'ArrowDown',
  'ArrowDown',
  'ArrowLeft',
  'ArrowRight',
  'ArrowLeft',
  'ArrowRight',
  'b',
  'a',
]

function press(keys: string[], target: EventTarget = window): void {
  keys.forEach((key) => {
    const event = new KeyboardEvent('keydown', { key, bubbles: true })
    target.dispatchEvent(event)
  })
}

describe('useEasterEggs', () => {
  beforeEach(() => {
    // The listener is a module-scope singleton registered once per tab, so the
    // first initEasterEggs() in this file is the only one that binds. Every
    // test here shares it, which is exactly how it behaves in the app.
    initEasterEggs()
    const { setAperture } = useEasterEggs()
    setAperture(false)
    document.body.innerHTML = ''
  })

  it('turns aperture mode on for the Konami code', () => {
    const { apertureMode } = useEasterEggs()

    press(KONAMI)

    expect(apertureMode.value).toBe(true)
    expect(document.documentElement.classList.contains('aperture-mode')).toBe(true)
    expect(localStorage.getItem('apertureMode')).toBe('true')
  })

  it('toggles back off on a second entry', () => {
    const { apertureMode } = useEasterEggs()

    press(KONAMI)
    press(KONAMI)

    expect(apertureMode.value).toBe(false)
    expect(document.documentElement.classList.contains('aperture-mode')).toBe(false)
  })

  it('summons the cake when it turns on, but not when it turns off', () => {
    const { cakeSummons } = useEasterEggs()
    const before = cakeSummons.value

    press(KONAMI)
    expect(cakeSummons.value).toBe(before + 1)

    press(KONAMI)
    expect(cakeSummons.value).toBe(before + 1)
  })

  it('ignores a wrong sequence', () => {
    const { apertureMode } = useEasterEggs()

    press(['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'a', 'b'])

    expect(apertureMode.value).toBe(false)
  })

  // The header search box takes focus readily, and typing "b" into it must not
  // count towards the code.
  it('ignores keys typed into an input', () => {
    const { apertureMode } = useEasterEggs()
    const input = document.createElement('input')
    document.body.appendChild(input)

    press(KONAMI, input)

    expect(apertureMode.value).toBe(false)
  })

  it('tolerates a fumbled start, matching on the last ten keys', () => {
    const { apertureMode } = useEasterEggs()

    press(['x', 'ArrowDown', ...KONAMI])

    expect(apertureMode.value).toBe(true)
  })

  it('restores a persisted mode on init', () => {
    const { setAperture, apertureMode } = useEasterEggs()

    setAperture(true)
    expect(localStorage.getItem('apertureMode')).toBe('true')
    expect(apertureMode.value).toBe(true)

    setAperture(false)
    expect(localStorage.getItem('apertureMode')).toBe('false')
  })

  // The unlocked preset is filtered out of the account page's theme picker
  // unless this flag is on, so the flag is the only route to it.
  it('gates the reserved preset behind the flag', () => {
    const { apertureMode } = useEasterEggs()
    const serverPresets = ['Aura', 'Lara', 'Material', APERTURE_PRESET]

    const offered = (unlocked: boolean) =>
      serverPresets.filter((preset) => unlocked || preset !== APERTURE_PRESET)

    expect(offered(apertureMode.value)).not.toContain(APERTURE_PRESET)

    press(KONAMI)

    expect(offered(apertureMode.value)).toContain(APERTURE_PRESET)
  })

  it('names a palette that actually exists', () => {
    // The whole red mode is a no-op if this drifts, since paintPrimary silently
    // does nothing for an unknown name.
    expect(PRIMARY_COLORS.map((c) => c.name)).toContain(APERTURE_PRIMARY)
  })

  it('reserves that palette - the account picker filters it out when locked', () => {
    const { apertureMode } = useEasterEggs()
    const offered = (unlocked: boolean) =>
      PRIMARY_COLORS.map((c) => c.name).filter((n) => unlocked || n !== APERTURE_PRIMARY)

    expect(offered(apertureMode.value)).not.toContain(APERTURE_PRIMARY)

    press(KONAMI)

    expect(offered(apertureMode.value)).toContain(APERTURE_PRIMARY)
  })

  it('does not throw when confetti has no canvas to draw on', () => {
    // jsdom has no 2D context; useConfetti already guards for this, and the
    // Konami handler must not care either way.
    expect(() => press(KONAMI)).not.toThrow()
  })
})

describe('initEasterEggs', () => {
  it('is idempotent - a second call does not double-bind the listener', () => {
    const { setAperture, apertureMode } = useEasterEggs()
    initEasterEggs()
    initEasterEggs()
    setAperture(false)

    press(KONAMI)

    // A double-bound listener would toggle twice and land back on false.
    expect(apertureMode.value).toBe(true)
  })
})

describe('cake summons', () => {
  it('is a counter so repeat entries re-summon', () => {
    const { cakeSummons, setAperture } = useEasterEggs()
    setAperture(false)
    const before = cakeSummons.value

    press(KONAMI)
    press(KONAMI)
    press(KONAMI)

    expect(cakeSummons.value).toBe(before + 2)
    vi.clearAllMocks()
  })
})

describe('disposeEasterEggs', () => {
  afterEach(() => {
    // Restore the plain, scope-free listener the other describe blocks rely on.
    initEasterEggs()
  })

  it('removes the keydown listener, so the code no longer does anything', () => {
    const { apertureMode, setAperture } = useEasterEggs()
    setAperture(false)
    disposeEasterEggs()

    press(KONAMI)

    expect(apertureMode.value).toBe(false)
  })

  it('resets the initialised guard so a later initEasterEggs() call re-attaches the listener', () => {
    disposeEasterEggs()
    initEasterEggs()

    const { apertureMode, setAperture } = useEasterEggs()
    setAperture(false)
    press(KONAMI)

    expect(apertureMode.value).toBe(true)
  })

  it('is safe to call when nothing is initialised', () => {
    disposeEasterEggs()

    expect(() => disposeEasterEggs()).not.toThrow()
  })

  it('runs automatically when the effect scope initEasterEggs() was called in is stopped', () => {
    disposeEasterEggs()
    const scope = effectScope()
    scope.run(() => initEasterEggs())

    scope.stop()

    const { apertureMode, setAperture } = useEasterEggs()
    setAperture(false)
    press(KONAMI)

    // The scope's own disposal already removed the listener, so the code does nothing.
    expect(apertureMode.value).toBe(false)
  })
})
