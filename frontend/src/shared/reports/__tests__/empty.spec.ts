import { describe, it, expect } from 'vitest'

import { REPORT_EMPTY, orDash } from '../utils/empty'

describe('orDash', () => {
  it('keeps text and replaces a missing or blank value', () => {
    expect(orDash('A-42')).toBe('A-42')
    expect(orDash(null)).toBe(REPORT_EMPTY)
    expect(orDash(undefined)).toBe(REPORT_EMPTY)
    expect(orDash('')).toBe(REPORT_EMPTY)
    expect(orDash('   ')).toBe(REPORT_EMPTY)
  })

  it('prints an en dash', () => {
    expect(REPORT_EMPTY).toBe('–')
  })
})
