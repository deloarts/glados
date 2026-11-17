import { describe, it, expect } from 'vitest'

import { makeSourceItemDemandResponse } from '@/test-utils/factories'

import { cancelBlockedReason } from '../sourceItemDemandCancel'

const LIVE_ACTIONS = ['cancel', 'fulfil', 'allocate', 'edit_quantity'] as const

describe('cancelBlockedReason', () => {
  it('lets a lot writer cancel a demand the server offers the cancel for', () => {
    const demand = makeSourceItemDemandResponse({ status: 'open', actions: [...LIVE_ACTIONS] })
    expect(cancelBlockedReason(demand, true)).toBe('')
  })

  it('names the missing permission first', () => {
    const demand = makeSourceItemDemandResponse({ status: 'open', actions: [...LIVE_ACTIONS] })
    expect(cancelBlockedReason(demand, false)).toBe('permission')
  })

  it('names a fulfilled or canceled demand as ended', () => {
    for (const status of ['fulfilled', 'canceled'] as const) {
      const demand = makeSourceItemDemandResponse({ status, actions: [] })
      expect(cancelBlockedReason(demand, true)).toBe('ended')
    }
  })

  it('names the started lot when a live demand is not offered the cancel', () => {
    const demand = makeSourceItemDemandResponse({
      status: 'allocated',
      actions: ['fulfil', 'allocate', 'edit_quantity'],
    })
    expect(cancelBlockedReason(demand, true)).toBe('lotStarted')
  })
})
