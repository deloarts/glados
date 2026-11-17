import { describe, expect, it } from 'vitest'

import { inputsEqual, resultDifferences, valuesEqual } from '../calculationCompare'

describe('valuesEqual', () => {
  it('treats floating point noise as equal but real changes as different', () => {
    expect(valuesEqual(0.1 + 0.2, 0.3)).toBe(true)
    expect(valuesEqual(25, 25.001)).toBe(false)
  })

  it('compares nested objects and arrays, null matching a missing key', () => {
    expect(valuesEqual({ a: [1, { b: 2 }], c: null }, { a: [1, { b: 2 }] })).toBe(true)
    expect(valuesEqual({ a: [1, 2] }, { a: [1, 2, 3] })).toBe(false)
  })
})

describe('inputsEqual', () => {
  it('ignores key order and treats missing as empty', () => {
    expect(inputsEqual({ d: '25', hole: 'H7' }, { hole: 'H7', d: '25' })).toBe(true)
    expect(inputsEqual({ d: '' }, {})).toBe(true)
    expect(inputsEqual({ d: '25' }, { d: '30' })).toBe(false)
  })
})

describe('resultDifferences', () => {
  it('lists the changed leaves by dotted path', () => {
    const saved = { hole: { upper: 21, lower: 0 }, fit: { type: 'clearance' } }
    const current = { hole: { upper: 25, lower: 0 }, fit: { type: 'clearance' } }
    expect(resultDifferences(saved, current)).toEqual([{ path: 'hole.upper', saved: 21, current: 25 }])
  })

  it('returns nothing for equal snapshots', () => {
    expect(resultDifferences({ a: 1 }, { a: 1 })).toEqual([])
  })
})
