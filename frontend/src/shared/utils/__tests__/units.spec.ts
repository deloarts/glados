import { describe, expect, it } from 'vitest'
import { formatUnit, quantityFractionDigits, unitsDiffer } from '../units'

describe('quantityFractionDigits', () => {
  it.each(['PCS', 'pcs', ' Set ', 'PAIR', 'UNIT', 'ROLL'])('takes no fraction for %s', (unit) => {
    expect(quantityFractionDigits(unit)).toBe(0)
  })

  it.each(['M', 'KG', 'L', 'H', ''])('takes three fraction digits for "%s"', (unit) => {
    expect(quantityFractionDigits(unit)).toBe(3)
  })

  it('takes three fraction digits without a unit', () => {
    expect(quantityFractionDigits(null)).toBe(3)
    expect(quantityFractionDigits(undefined)).toBe(3)
  })
})

describe('unitsDiffer', () => {
  it.each([
    ['PCS', 'pcs', false],
    [' M ', 'M', false],
    ['PCS', 'M', true],
    ['PCS', null, false],
  ] as const)('compares %s with %s', (demand, line, differ) => {
    expect(unitsDiffer(demand, line)).toBe(differ)
  })
})

describe('formatUnit', () => {
  it.each(['M2', 'm2', ' m2 '])('labels %s by its code, ignoring case', (unit) => {
    expect(formatUnit(unit)).toBe('m²')
  })

  it('passes an unknown unit through unchanged', () => {
    expect(formatUnit('furlong')).toBe('furlong')
  })
})
