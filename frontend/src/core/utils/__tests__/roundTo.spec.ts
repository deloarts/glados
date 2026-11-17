import { describe, it, expect } from 'vitest'

import { roundTo, withoutNegativeZero } from '../numbers'

describe('roundTo', () => {
  it('rounds to the given decimals the way toFixed does', () => {
    expect(roundTo(0.1 + 0.2, 6)).toBe(0.3)
    expect(roundTo(2.3333333, 2)).toBe(2.33)
    expect(roundTo(1.005, 2)).toBe(Number((1.005).toFixed(2)))
    expect(roundTo(5, 3)).toBe(5)
  })

  it('keeps the sign of a tiny negative value as -0', () => {
    expect(Object.is(roundTo(-0.0000001, 6), -0)).toBe(true)
  })
})

describe('withoutNegativeZero', () => {
  it('turns -0 into 0 and leaves other values alone', () => {
    expect(Object.is(withoutNegativeZero(-0), 0)).toBe(true)
    expect(withoutNegativeZero(-1.5)).toBe(-1.5)
    expect(withoutNegativeZero(2)).toBe(2)
  })
})
