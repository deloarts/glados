import { describe, it, expect } from 'vitest'

import { legalBasisFor, legalBasisOutdated } from '../legalBasis'

const BEFORE = new Date(2026, 9, 21)
const AFTER = new Date(2027, 0, 20)

describe('legal basis', () => {
  it('preselects the act that applies on the planned date, or today without one', () => {
    expect(legalBasisFor('2027-01-19', BEFORE)).toBe('directive')
    expect(legalBasisFor('2027-01-20', BEFORE)).toBe('regulation')
    expect(legalBasisFor(null, BEFORE)).toBe('directive')
    expect(legalBasisFor(null, AFTER)).toBe('regulation')
  })

  it('flags only the Directive for a placing on the market once the Regulation applies', () => {
    expect(legalBasisOutdated('directive', '2027-01-20', BEFORE)).toBe(true)
    expect(legalBasisOutdated('directive', '2027-01-19', BEFORE)).toBe(false)
    expect(legalBasisOutdated('directive', null, AFTER)).toBe(true)
    expect(legalBasisOutdated('regulation', '2026-11-01', BEFORE)).toBe(false)
    expect(legalBasisOutdated(null, '2027-03-01', BEFORE)).toBe(false)
  })
})
