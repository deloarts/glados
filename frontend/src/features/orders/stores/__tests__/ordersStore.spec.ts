import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { OrderFilterParams } from '../../types/ordersRequest'
import type { OrderResponse } from '../../types/ordersResponse'

const getOrdersMock =
  vi.fn<(params?: OrderFilterParams) => Promise<PageResponse<OrderResponse>>>()

vi.mock('../../api/getOrders', () => ({
  getOrders: (params?: OrderFilterParams) => getOrdersMock(params),
}))

import { useOrdersStore } from '../ordersStore'
import { makeOrderResponse } from '@/test-utils/factories'

/**
 * A promise plus its resolve, so a test can control exactly when a given
 * call settles instead of racing on real timers; mirrors the helper in
 * useSequencedFetch.spec.ts.
 */
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function page(items: OrderResponse[]): PageResponse<OrderResponse> {
  return { items, total: items.length, limit: null, skip: 0 }
}

describe('ordersStore.refresh, concurrency', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getOrdersMock.mockReset()
  })

  it('populates items/total from a single refresh', async () => {
    getOrdersMock.mockResolvedValue(page([makeOrderResponse()]))
    const store = useOrdersStore()

    await store.refresh()

    expect(store.items).toHaveLength(1)
    expect(store.total).toBe(1)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('discards a slow response that resolves after a faster, later refresh (last-wins)', async () => {
    const slow = deferred<PageResponse<OrderResponse>>()
    const fast = deferred<PageResponse<OrderResponse>>()
    getOrdersMock.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)
    const store = useOrdersStore()

    // Two overlapping refreshes, e.g. a filter change firing a second
    // request before the first (broader, slower) one has come back.
    const slowCall = store.refresh({ search: 'slow' })
    const fastCall = store.refresh({ search: 'fast' })

    // The second (fast) call resolves first...
    fast.resolve(page([makeOrderResponse({ id: 2, order_number: 'ORD-2' })]))
    await fastCall
    expect(store.items.map((i) => i.order_number)).toEqual(['ORD-2'])
    expect(store.loading).toBe(false)

    // ...then the stale first call lands. It must be discarded, not
    // overwrite the later call's result.
    slow.resolve(page([makeOrderResponse({ id: 1, order_number: 'ORD-1' })]))
    await slowCall

    expect(store.items.map((i) => i.order_number)).toEqual(['ORD-2'])
    expect(store.total).toBe(1)
    expect(store.loading).toBe(false)
  })
})
