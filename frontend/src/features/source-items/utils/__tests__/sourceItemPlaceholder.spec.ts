import { describe, it, expect } from 'vitest'

import { detectDimensionShape, sourceItemPlaceholder } from '../sourceItemPlaceholder'

describe('detectDimensionShape', () => {
  it('detects a box', () => {
    expect(detectDimensionShape('100 × 200 × 20')).toBe('box')
  })

  it('detects a hollow box', () => {
    expect(detectDimensionShape('100 × 200 × 20 × 5')).toBe('hollow-box')
  })

  it('detects a rod', () => {
    expect(detectDimensionShape('Ø20 × 100')).toBe('rod')
  })

  it('detects a hollow rod', () => {
    expect(detectDimensionShape('Ø100 × 20 × 5')).toBe('hollow-rod')
  })

  it('still detects a shape typed with legacy separators ("x" and lowercase "ø")', () => {
    expect(detectDimensionShape('100 x 200 x 20')).toBe('box')
    expect(detectDimensionShape('ø20 x 100')).toBe('rod')
  })

  it('returns null for a custom, empty, or null dimension', () => {
    expect(detectDimensionShape('custom shape')).toBeNull()
    expect(detectDimensionShape('')).toBeNull()
    expect(detectDimensionShape('   ')).toBeNull()
    expect(detectDimensionShape(null)).toBeNull()
    expect(detectDimensionShape(undefined)).toBeNull()
  })
})

describe('sourceItemPlaceholder', () => {
  it('maps a box to the block placeholder pair', () => {
    const placeholder = sourceItemPlaceholder('100 × 200 × 20')
    expect(placeholder?.image).toContain('block')
    expect(placeholder?.mesh).toContain('block')
  })

  it('maps a hollow box to the profile placeholder pair', () => {
    const placeholder = sourceItemPlaceholder('100 × 200 × 20 × 5')
    expect(placeholder?.image).toContain('profile')
    expect(placeholder?.mesh).toContain('profile')
  })

  it('maps a rod to the turned placeholder pair', () => {
    const placeholder = sourceItemPlaceholder('Ø20 × 100')
    expect(placeholder?.image).toContain('turned')
    expect(placeholder?.mesh).toContain('turned')
  })

  it('maps a hollow rod to the tube placeholder pair', () => {
    const placeholder = sourceItemPlaceholder('Ø100 × 20 × 5')
    expect(placeholder?.image).toContain('tube')
    expect(placeholder?.mesh).toContain('tube')
  })

  it('still detects a shape typed with legacy separators ("x" and lowercase "ø")', () => {
    expect(sourceItemPlaceholder('100 x 200 x 20')?.image).toContain('block')
    expect(sourceItemPlaceholder('ø100 x 20 x 5')?.mesh).toContain('tube')
  })

  it('returns null for a custom, empty, or null dimension - no placeholder at all', () => {
    expect(sourceItemPlaceholder('custom shape')).toBeNull()
    expect(sourceItemPlaceholder('')).toBeNull()
    expect(sourceItemPlaceholder(null)).toBeNull()
    expect(sourceItemPlaceholder(undefined)).toBeNull()
  })
})
