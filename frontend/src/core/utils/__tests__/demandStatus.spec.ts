import { describe, it, expect } from 'vitest'

import { DEMAND_STATUSES, DEMAND_STATUS_SEVERITY } from '../demandStatus'

// This module is the canonical source for the demand-status list and its
// severity map, which every demand family's views import directly.

describe('DEMAND_STATUSES', () => {
  it('lists the five demand-lifecycle statuses in order', () => {
    expect(DEMAND_STATUSES).toEqual(['open', 'allocated', 'ordered', 'fulfilled', 'canceled'])
  })
})

describe('DEMAND_STATUS_SEVERITY', () => {
  it('maps every status to its canonical OpenVue severity', () => {
    expect(DEMAND_STATUS_SEVERITY).toEqual({
      open: 'info',
      allocated: 'warn',
      ordered: 'help',
      fulfilled: 'success',
      canceled: 'secondary',
    })
  })
})
