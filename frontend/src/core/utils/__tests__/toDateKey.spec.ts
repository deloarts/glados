import { describe, expect, it } from 'vitest'

import { dateToParam, toDateKey } from '../dates'

describe('toDateKey', () => {
  it('keeps the local calendar day of a picked local midnight', () => {
    expect(toDateKey(new Date(2026, 9, 9, 0, 0, 0))).toBe('2026-10-09')
  })

  it('keeps the local calendar day late in the evening', () => {
    expect(toDateKey(new Date(2026, 0, 31, 23, 59, 59))).toBe('2026-01-31')
  })

  it('pads month and day to two digits', () => {
    expect(toDateKey(new Date(2026, 2, 5))).toBe('2026-03-05')
  })
})

describe('dateToParam', () => {
  it('passes null through and delegates a date to toDateKey', () => {
    expect(dateToParam(null)).toBeNull()
    expect(dateToParam(new Date(2026, 9, 9))).toBe('2026-10-09')
  })
})
