import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { LotFilterParams } from '../../types/productionLotsRequest'
import type { LotSummaryResponse } from '../../types/productionLotsResponse'

const getLotsMock =
  vi.fn<(params?: LotFilterParams) => Promise<PageResponse<LotSummaryResponse>>>()

vi.mock('../../api/getLots', () => ({ getLots: (params?: LotFilterParams) => getLotsMock(params) }))

import { useProductionLotsStore } from '../productionLotsStore'
import { makeLotSummaryResponse } from '@/test-utils/factories'

/**
 * A promise plus its resolve, so a test can control exactly when a given
 * call settles instead of racing on real timers. Mirrors the helper in
 * useSequencedFetch.spec.ts.
 */
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function makeLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLotSummaryResponse({ public_id: '22222222-2222-2222-2222-222222222222', ...overrides })
}

function page(items: LotSummaryResponse[]): PageResponse<LotSummaryResponse> {
  return { items, total: items.length, limit: null, skip: 0 }
}

describe('productionLotsStore.refresh, concurrency', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getLotsMock.mockReset()
  })

  it('populates items/total from a single refresh', async () => {
    getLotsMock.mockResolvedValue(page([makeLot()]))
    const store = useProductionLotsStore()

    await store.refresh()

    expect(store.items).toHaveLength(1)
    expect(store.total).toBe(1)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('discards a slow response that resolves after a faster, later refresh (last-wins)', async () => {
    const slow = deferred<PageResponse<LotSummaryResponse>>()
    const fast = deferred<PageResponse<LotSummaryResponse>>()
    getLotsMock.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)
    const store = useProductionLotsStore()

    // Two overlapping refreshes, e.g. a filter change firing a second
    // request before the first (broader, slower) one has come back.
    const slowCall = store.refresh({ search: 'slow' })
    const fastCall = store.refresh({ search: 'fast' })

    // The second (fast) call resolves first...
    fast.resolve(page([makeLot({ id: 2, lot_number: 'LOT-2' })]))
    await fastCall
    expect(store.items.map((i) => i.lot_number)).toEqual(['LOT-2'])
    expect(store.loading).toBe(false)

    // ...then the stale first call lands and must be discarded, not
    // overwrite the later call's result.
    slow.resolve(page([makeLot({ id: 1, lot_number: 'LOT-1' })]))
    await slowCall

    expect(store.items.map((i) => i.lot_number)).toEqual(['LOT-2'])
    expect(store.total).toBe(1)
    expect(store.loading).toBe(false)
  })
})
