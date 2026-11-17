import { describe, it, expect } from 'vitest'

import { areDimensionsEquivalent, canonicalizeDimension } from '../dimensionSpec'

describe('canonicalizeDimension / areDimensionsEquivalent', () => {
  it('treats any permutation of a box dimension as equivalent', () => {
    expect(areDimensionsEquivalent('100 × 200 × 20', '200 × 100 × 20')).toBe(true)
    expect(areDimensionsEquivalent('100 × 200 × 20', '20 × 200 × 100')).toBe(true)
    expect(canonicalizeDimension('100 × 200 × 20')).toBe('200 × 100 × 20')
  })

  it('normalizes trailing-zero/decimal number formatting', () => {
    expect(areDimensionsEquivalent('100.0 × 200 × 20', '100 × 200 × 20')).toBe(true)
    expect(areDimensionsEquivalent('12.50 × 1 × 1', '12.5 × 1 × 1')).toBe(true)
    expect(canonicalizeDimension('100.00 × 1 × 1')).toBe('100 × 1 × 1')
  })

  it('normalizes an ASCII "x" separator the same as "×"', () => {
    expect(areDimensionsEquivalent('100 x 200 x 20', '100 × 200 × 20')).toBe(true)
    expect(areDimensionsEquivalent('100X200X20', '200 × 100 × 20')).toBe(true)
  })

  it("does not permute a rod's diameter and length", () => {
    expect(areDimensionsEquivalent('Ø20 × 100', 'Ø100 × 20')).toBe(false)
    expect(areDimensionsEquivalent('Ø20 × 100', 'Ø20 × 100')).toBe(true)
  })

  it("does not permute a hollow rod's numbers", () => {
    expect(areDimensionsEquivalent('Ø100 × 20 × 5', 'Ø5 × 20 × 100')).toBe(false)
  })

  it("does not permute a hollow box's numbers", () => {
    expect(areDimensionsEquivalent('100 × 200 × 20 × 5', '5 × 20 × 200 × 100')).toBe(false)
    expect(areDimensionsEquivalent('100 × 200 × 20 × 5', '100 × 200 × 20 × 5')).toBe(true)
  })

  it('collapses whitespace on custom (unmatched) text without altering content', () => {
    expect(canonicalizeDimension('  custom   shape  ')).toBe('custom shape')
    expect(areDimensionsEquivalent('custom shape', 'custom  shape')).toBe(true)
    expect(areDimensionsEquivalent('custom shape A', 'custom shape B')).toBe(false)
  })

  it('treats null/empty as equal only to each other', () => {
    expect(canonicalizeDimension(null)).toBeNull()
    expect(canonicalizeDimension(undefined)).toBeNull()
    expect(canonicalizeDimension('')).toBeNull()
    expect(canonicalizeDimension('   ')).toBeNull()
    expect(areDimensionsEquivalent(null, undefined)).toBe(true)
    expect(areDimensionsEquivalent(null, '')).toBe(true)
    expect(areDimensionsEquivalent(null, '100 × 200 × 20')).toBe(false)
  })
})
