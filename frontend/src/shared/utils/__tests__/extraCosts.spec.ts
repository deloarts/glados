import { describe, it, expect } from 'vitest'

import { extraCostDraftError, extraCostName, signedExtraCost } from '../extraCosts'

describe('extraCosts', () => {
  it('subtracts a discount and adds every other kind', () => {
    expect(signedExtraCost('discount', 300)).toBe(-300)
    expect(signedExtraCost('shipping', 300)).toBe(300)
  })

  it('names a cost by its label, else by its kind', () => {
    const t = (key: string) => `[${key}]`
    expect(extraCostName(t, { kind: 'other', label: 'Pallet deposit' })).toBe('Pallet deposit')
    expect(extraCostName(t, { kind: 'shipping', label: null })).toBe(
      '[common.extraCosts.kinds.shipping]',
    )
  })

  it('finds a missing amount and a missing label', () => {
    const base = { label: '', note: '', lineId: null }
    expect(extraCostDraftError([{ ...base, kind: 'shipping', amount: 100 }])).toBeNull()
    expect(extraCostDraftError([{ ...base, kind: 'shipping', amount: null }])).toBe(
      'common.extraCosts.errors.amount',
    )
    expect(extraCostDraftError([{ ...base, kind: 'other', amount: 100 }])).toBe(
      'common.extraCosts.errors.label',
    )
  })
})
