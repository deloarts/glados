import { describe, it, expect } from 'vitest'

import { demandDisplayStatus } from '../demandDisplayStatus'
import type { DemandSummaryResponse } from '@/features/bought-items'


function summary(overrides: Partial<DemandSummaryResponse> = {}): DemandSummaryResponse {
  return {
    allocated: 0,
    delivered: 0,
    demand_item_id: 1,
    fulfilled_from_stock: 0,
    in_transit: 0,
    is_fully_allocated: false,
    is_fully_delivered: false,
    order_ids: [],
    order_numbers: [],
    ordered: 0,
    pending: 0,
    remaining: 10,
    substitutions: [],
    total: 10,
    unallocated: 10,
    unit: 'PCS',
    unit_mismatch: false,
    ...overrides,
  }
}

describe('demandDisplayStatus', () => {
  it('shows a manually fulfilled demand as fulfilled although its pieces are only ordered', () => {
    const ordered = summary({ allocated: 10, ordered: 10 })
    expect(demandDisplayStatus({ status: 'fulfilled' }, ordered)).toBe('fulfilled')
  })

  it('shows a canceled demand as canceled whatever its allocations say', () => {
    expect(demandDisplayStatus({ status: 'canceled' }, summary({ allocated: 10 }))).toBe('canceled')
  })

  it('refines an allocated demand by its allocations', () => {
    expect(demandDisplayStatus({ status: 'allocated' }, summary({ allocated: 4 }))).toBe('partially_allocated')
    expect(demandDisplayStatus({ status: 'allocated' }, summary({ allocated: 10 }))).toBe('allocated')
    expect(demandDisplayStatus({ status: 'allocated' }, summary({ allocated: 10, ordered: 4 }))).toBe(
      'partially_ordered',
    )
    expect(
      demandDisplayStatus({ status: 'allocated' }, summary({ allocated: 10, ordered: 10, delivered: 4 })),
    ).toBe('partially_delivered')
  })

  it('refines an ordered demand only to partially delivered', () => {
    const delivering = summary({ allocated: 10, ordered: 10, delivered: 4 })
    expect(demandDisplayStatus({ status: 'ordered' }, delivering)).toBe('partially_delivered')
    expect(demandDisplayStatus({ status: 'ordered' }, summary({ allocated: 10, ordered: 10 }))).toBe('ordered')
  })

  it('keeps the stored status when the allocations contradict it', () => {
    const delivered = summary({ allocated: 10, ordered: 10, delivered: 10 })
    expect(demandDisplayStatus({ status: 'ordered' }, delivered)).toBe('ordered')
    expect(demandDisplayStatus({ status: 'open' }, summary({ allocated: 4 }))).toBe('open')
  })

  it('shows the stored status while no summary is loaded', () => {
    expect(demandDisplayStatus({ status: 'allocated' }, undefined)).toBe('allocated')
  })
})
