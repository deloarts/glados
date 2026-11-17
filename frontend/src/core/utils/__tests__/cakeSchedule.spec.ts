import { describe, it, expect } from 'vitest'

import { isCakeWindowOpen, isCakeWindowStale, rollCakeWindow, weekKeyOf } from '../cakeSchedule'

/** A sequence-backed stand-in for Math.random so a roll is fully pinned. */
function seeded(values: number[]): () => number {
  let index = 0
  return () => values[index++ % values.length]!
}

describe('weekKeyOf', () => {
  it('gives every day of a week the same key', () => {
    // Monday 2026-08-10 through Sunday 2026-08-16.
    const keys = [10, 11, 12, 13, 14, 15, 16].map((day) => weekKeyOf(new Date(2026, 7, day, 12, 0)))
    expect(new Set(keys).size).toBe(1)
    expect(keys[0]).toBe('2026-08-10')
  })

  it('puts Sunday in the week that started six days earlier, not the next one', () => {
    expect(weekKeyOf(new Date(2026, 7, 16, 23, 59))).toBe('2026-08-10')
    expect(weekKeyOf(new Date(2026, 7, 17, 0, 1))).toBe('2026-08-17')
  })
})

describe('rollCakeWindow', () => {
  it('lands inside 09:00-14:00 and lasts about an hour', () => {
    // Sweep the whole random space rather than trusting one sample: the
    // 09:00-14:00 promise is the only thing a user ever notices about this.
    for (let step = 0; step <= 20; step++) {
      const r = step / 20
      const window = rollCakeWindow(new Date(2026, 7, 10, 7, 0), seeded([r]))
      expect(window.startsAt).not.toBeNull()

      const start = new Date(window.startsAt!)
      const end = new Date(window.startsAt! + window.durationMs)
      const startMinutes = start.getHours() * 60 + start.getMinutes()
      const endMinutes = end.getHours() * 60 + end.getMinutes()

      expect(startMinutes).toBeGreaterThanOrEqual(9 * 60)
      expect(endMinutes).toBeLessThanOrEqual(14 * 60)
      expect(window.durationMs).toBeGreaterThanOrEqual(50 * 60_000)
      expect(window.durationMs).toBeLessThanOrEqual(70 * 60_000)
    }
  })

  it('never rolls a slot that has already passed', () => {
    // Monday, 13:30: past the latest possible start, so today is out and it
    // has to fall on a later weekday of the same week.
    const now = new Date(2026, 7, 10, 13, 30)
    const window = rollCakeWindow(now, seeded([0]))

    expect(window.startsAt).not.toBeNull()
    expect(window.startsAt!).toBeGreaterThan(now.getTime())
  })

  it('can still land later the same day', () => {
    const now = new Date(2026, 7, 10, 8, 0)
    const window = rollCakeWindow(now, seeded([0]))
    expect(new Date(window.startsAt!).getDate()).toBe(10)
  })

  it('only ever picks weekdays', () => {
    for (let step = 0; step <= 20; step++) {
      const window = rollCakeWindow(new Date(2026, 7, 10, 7, 0), seeded([step / 20]))
      const weekday = new Date(window.startsAt!).getDay()
      expect(weekday).toBeGreaterThanOrEqual(1)
      expect(weekday).toBeLessThanOrEqual(5)
    }
  })

  it('yields no cake when the week has run out of slots', () => {
    // Friday 2026-08-14, 13:45: no weekday slot left before Monday.
    const window = rollCakeWindow(new Date(2026, 7, 14, 13, 45), seeded([0.5]))
    expect(window.startsAt).toBeNull()
    expect(isCakeWindowOpen(window, new Date(2026, 7, 14, 13, 50))).toBe(false)
  })
})

describe('isCakeWindowOpen', () => {
  const window = {
    weekKey: '2026-08-10',
    startsAt: new Date(2026, 7, 12, 10, 0).getTime(),
    durationMs: 60 * 60_000,
  }

  it('is closed before, open during, closed after', () => {
    expect(isCakeWindowOpen(window, new Date(2026, 7, 12, 9, 59))).toBe(false)
    expect(isCakeWindowOpen(window, new Date(2026, 7, 12, 10, 30))).toBe(true)
    expect(isCakeWindowOpen(window, new Date(2026, 7, 12, 11, 0))).toBe(false)
  })

  it('is closed for a null window', () => {
    expect(isCakeWindowOpen(null, new Date(2026, 7, 12, 10, 30))).toBe(false)
  })
})

describe('isCakeWindowStale', () => {
  const window = { weekKey: '2026-08-10', startsAt: 0, durationMs: 0 }

  it('is fresh within its own week and stale in the next', () => {
    expect(isCakeWindowStale(window, new Date(2026, 7, 16, 23, 0))).toBe(false)
    expect(isCakeWindowStale(window, new Date(2026, 7, 17, 0, 1))).toBe(true)
  })

  it('treats a missing window as stale so a first load rolls one', () => {
    expect(isCakeWindowStale(null, new Date(2026, 7, 12))).toBe(true)
  })
})
