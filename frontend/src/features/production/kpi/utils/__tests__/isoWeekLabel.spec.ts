import { describe, it, expect } from 'vitest'

import { formatIsoWeekLabel, isoWeekNumber } from '../isoWeekLabel'

describe('isoWeekNumber', () => {
  it('extracts the week number out of a "YYYY-Www" key', () => {
    expect(isoWeekNumber('2026-W07')).toBe(7)
    expect(isoWeekNumber('2026-W52')).toBe(52)
  })

  it('returns 0 for a malformed key rather than throwing', () => {
    expect(isoWeekNumber('not-a-week')).toBe(0)
    expect(isoWeekNumber('')).toBe(0)
  })
})

describe('formatIsoWeekLabel', () => {
  it('prefixes the extracted week number with the given prefix', () => {
    expect(formatIsoWeekLabel('2026-W07', 'W')).toBe('W7')
    expect(formatIsoWeekLabel('2026-W07', 'KW')).toBe('KW7')
  })
})
