import { describe, it, expect } from 'vitest'

import { formatDuration, formatSignedDuration } from '../formatDuration'

describe('formatDuration', () => {
  it('renders hours and zero-padded minutes', () => {
    expect(formatDuration(7 * 3600 + 42 * 60)).toBe('7:42')
    expect(formatDuration(5 * 60)).toBe('0:05')
    expect(formatDuration(0)).toBe('0:00')
  })

  it('does not wrap hours at a day', () => {
    expect(formatDuration(162 * 3600 + 30 * 60)).toBe('162:30')
  })

  it('drops seconds towards zero', () => {
    expect(formatDuration(7 * 3600 + 42 * 60 + 59)).toBe('7:42')
    expect(formatDuration(-(15 * 60 + 59))).toBe('-0:15')
  })

  it('shows a minus for a negative duration and nothing for less than a minute', () => {
    expect(formatDuration(-(3600 + 60))).toBe('-1:01')
    expect(formatDuration(-59)).toBe('0:00')
  })
})

describe('formatSignedDuration', () => {
  it('prefixes a positive balance with a plus', () => {
    expect(formatSignedDuration(7 * 3600 + 42 * 60)).toBe('+7:42')
  })

  it('prefixes a negative balance with a minus', () => {
    expect(formatSignedDuration(-15 * 60)).toBe('-0:15')
    expect(formatSignedDuration(-(10 * 3600 + 5 * 60))).toBe('-10:05')
  })

  it('shows zero, and anything under a minute, without a sign', () => {
    expect(formatSignedDuration(0)).toBe('0:00')
    expect(formatSignedDuration(59)).toBe('0:00')
    expect(formatSignedDuration(-59)).toBe('0:00')
  })
})
