import { describe, it, expect } from 'vitest'

import { finiteNumberOrNull, isPlainRecord, plainRecordOrNull } from '../guards'

describe('isPlainRecord / plainRecordOrNull', () => {
  it('accepts JSON objects only', () => {
    const value = { a: 1 }
    expect(isPlainRecord(value)).toBe(true)
    expect(plainRecordOrNull(value)).toBe(value)
    for (const other of [null, undefined, [], 'x', 3, true]) {
      expect(isPlainRecord(other)).toBe(false)
      expect(plainRecordOrNull(other)).toBeNull()
    }
  })
})

describe('finiteNumberOrNull', () => {
  it('passes finite numbers and rejects the rest', () => {
    expect(finiteNumberOrNull(0)).toBe(0)
    expect(finiteNumberOrNull(-2.5)).toBe(-2.5)
    for (const other of [Number.NaN, Number.POSITIVE_INFINITY, '3', null, undefined]) {
      expect(finiteNumberOrNull(other)).toBeNull()
    }
  })
})
