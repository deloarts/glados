import { describe, it, expect } from 'vitest'

import { parseSavedSize, savedString } from '../savedInputs'

describe('savedString', () => {
  it('passes text and treats anything else as missing', () => {
    expect(savedString('M8')).toBe('M8')
    expect(savedString(undefined)).toBeNull()
    expect(savedString(8)).toBeNull()
  })
})

describe('parseSavedSize', () => {
  it('falls back silently when the size is missing', () => {
    expect(parseSavedSize(null, 25, 100)).toEqual({ size: 25, invalid: false })
  })

  it('reads a size with a decimal point or comma', () => {
    expect(parseSavedSize('12.5', 25, 100)).toEqual({ size: 12.5, invalid: false })
    expect(parseSavedSize('12,5', 25, 100)).toEqual({ size: 12.5, invalid: false })
    expect(parseSavedSize('100', 25, 100)).toEqual({ size: 100, invalid: false })
  })

  it('falls back and flags a size outside (0, max] or not a number', () => {
    for (const raw of ['0', '-3', '101', 'abc', 'Infinity']) {
      expect(parseSavedSize(raw, 25, 100)).toEqual({ size: 25, invalid: true })
    }
  })
})
