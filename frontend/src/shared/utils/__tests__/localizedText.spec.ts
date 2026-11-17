import { describe, expect, it } from 'vitest'

import { cleanLocalizedText, resolveLocalizedText } from '../localizedText'

describe('resolveLocalizedText', () => {
  it('returns the text in the requested language', () => {
    expect(resolveLocalizedText({ enGB: 'Extended', deAT: 'Ausgefahren' }, 'deAT', 'enGB')).toBe(
      'Ausgefahren',
    )
  })

  it('falls back to the default language', () => {
    expect(resolveLocalizedText({ enGB: 'Extended' }, 'deAT', 'enGB')).toBe('Extended')
  })

  it('falls back to any language when neither is present', () => {
    expect(resolveLocalizedText({ deAT: 'Ausgefahren' }, 'enGB', 'enGB')).toBe('Ausgefahren')
  })

  it('returns an empty string for a missing or empty label', () => {
    expect(resolveLocalizedText(null, 'enGB', 'enGB')).toBe('')
    expect(resolveLocalizedText({}, 'enGB', 'enGB')).toBe('')
  })
})

describe('cleanLocalizedText', () => {
  it('trims values and drops empty ones', () => {
    expect(cleanLocalizedText({ enGB: '  Open ', deAT: '   ' })).toEqual({ enGB: 'Open' })
  })
})
