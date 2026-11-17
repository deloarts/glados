import { describe, expect, it } from 'vitest'

import { MIN_TEXT_CONTRAST, apcaContrast, readableTextColor, textContrast } from '../contrast'

describe('apcaContrast', () => {
  it('matches the APCA reference values for black and white', () => {
    expect(apcaContrast('#000000', '#ffffff')).toBeCloseTo(106.04, 1)
    expect(apcaContrast('#ffffff', '#000000')).toBeCloseTo(-107.88, 1)
  })

  it('is zero for identical colours and null for a half-typed hex code', () => {
    expect(apcaContrast('#888888', '#888888')).toBe(0)
    expect(apcaContrast('#12', '#ffffff')).toBeNull()
  })
})

describe('readableTextColor', () => {
  // The WCAG 2 ratio picks black on all of these, which reads worse.
  it.each(['#2196f3', '#43a047', '#e53935', '#f57c00', '#6366f1'])(
    'prefers white on the saturated mid tone %s',
    (background) => {
      expect(readableTextColor(background)).toBe('#ffffff')
    },
  )

  it.each(['#ffeb3b', '#ffc107', '#8bc34a', '#ffffff'])('prefers black on the light colour %s', (background) => {
    expect(readableTextColor(background)).toBe('#000000')
  })
})

describe('textContrast', () => {
  it('accepts white on a medium blue and rejects white on yellow', () => {
    expect(textContrast('#ffffff', '#2196f3')).toBeGreaterThanOrEqual(MIN_TEXT_CONTRAST)
    expect(textContrast('#ffffff', '#ffeb3b')).toBeLessThan(MIN_TEXT_CONTRAST)
  })
})
