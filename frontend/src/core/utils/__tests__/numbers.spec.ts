import { describe, it, expect } from 'vitest'

import { formatDecimal } from '../numbers'

describe('formatDecimal', () => {
  it('keeps whole numbers whole', () => {
    expect(formatDecimal(5)).toBe('5')
    expect(formatDecimal(0)).toBe('0')
    expect(formatDecimal(-3)).toBe('-3')
  })

  it('rounds to a single decimal place', () => {
    expect(formatDecimal(2.34)).toBe('2.3')
    expect(formatDecimal(2.35)).toBe('2.4')
    expect(formatDecimal(2.99)).toBe('3')
  })

  it('tames float noise from the backend', () => {
    expect(formatDecimal(4.000000000000001)).toBe('4')
    expect(formatDecimal(2.3333333333333335)).toBe('2.3')
    expect(formatDecimal(0.1 + 0.2)).toBe('0.3')
  })

  it('falls back for null, undefined and non-finite values', () => {
    expect(formatDecimal(null)).toBe('-')
    expect(formatDecimal(undefined)).toBe('-')
    expect(formatDecimal(Number.NaN)).toBe('-')
    expect(formatDecimal(Number.POSITIVE_INFINITY)).toBe('-')
  })

  it('accepts a custom fallback', () => {
    expect(formatDecimal(null, '0')).toBe('0')
  })
})
