import { describe, it, expect } from 'vitest'

import { fullQueueIdsForColumn } from '../queueReorderPayload'

// ProductionQueueBoard.vue's reorder payload building, a plain module so it
// can be tested without exposing the component's internals.

function order(overrides: { id: number; pinned?: boolean; status?: string }) {
  return { pinned: false, status: 'queued', ...overrides } as {
    id: number
    pinned: boolean
    status: 'queued' | 'paused' | 'in_progress' | 'completed' | 'canceled'
  }
}

describe('fullQueueIdsForColumn', () => {
  it('returns the visible ids in order when there is nothing pinned/locked and no future orders', () => {
    const visible = [order({ id: 2 }), order({ id: 1 }), order({ id: 3 })]

    expect(fullQueueIdsForColumn(visible, [])).toEqual([2, 1, 3])
  })

  it('excludes pinned orders from the visible half', () => {
    const visible = [order({ id: 1 }), order({ id: 2, pinned: true }), order({ id: 3 })]

    expect(fullQueueIdsForColumn(visible, [])).toEqual([1, 3])
  })

  it('excludes in-progress orders from the visible half', () => {
    const visible = [order({ id: 1, status: 'in_progress' }), order({ id: 2 })]

    expect(fullQueueIdsForColumn(visible, [])).toEqual([2])
  })

  it('appends future orders after the visible ones, in their existing relative order', () => {
    const visible = [order({ id: 1 })]
    const future = [order({ id: 10 }), order({ id: 11 })]

    expect(fullQueueIdsForColumn(visible, future)).toEqual([1, 10, 11])
  })

  it('excludes a future order already present in the visible half (no duplicate ids)', () => {
    const visible = [order({ id: 1 })]
    const future = [order({ id: 1 }), order({ id: 10 })]

    expect(fullQueueIdsForColumn(visible, future)).toEqual([1, 10])
  })

  it('excludes pinned/in-progress future orders', () => {
    const visible = [order({ id: 1 })]
    const future = [
      order({ id: 10, pinned: true }),
      order({ id: 11, status: 'in_progress' }),
      order({ id: 12 }),
    ]

    expect(fullQueueIdsForColumn(visible, future)).toEqual([1, 12])
  })

  it('excludes completed/canceled future orders - only queued/paused ones belong in the sequence space', () => {
    const visible = [order({ id: 1 })]
    const future = [
      order({ id: 10, status: 'completed' }),
      order({ id: 11, status: 'canceled' }),
      order({ id: 12, status: 'paused' }),
    ]

    expect(fullQueueIdsForColumn(visible, future)).toEqual([1, 12])
  })

  it('returns an empty array when there is nothing visible and nothing future', () => {
    expect(fullQueueIdsForColumn([], [])).toEqual([])
  })
})
