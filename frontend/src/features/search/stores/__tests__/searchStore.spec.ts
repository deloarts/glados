import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type {
  GlobalSearchGroup,
  GlobalSearchHit,
  GlobalSearchResponse,
} from '../../types/globalSearchResponse'

const globalSearchMock = vi.fn<(q: string, limit?: number) => Promise<GlobalSearchResponse>>()

vi.mock('../../api/globalSearch', () => ({
  globalSearch: (q: string, limit?: number) => globalSearchMock(q, limit),
}))

import { useSearchStore } from '../searchStore'

/**
 * A promise plus its resolve, so a test can control exactly when a given
 * call settles instead of racing on real timers. Mirrors the helper in
 * ordersStore.spec.ts.
 */
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function makeHit(overrides: Partial<GlobalSearchHit> = {}): GlobalSearchHit {
  return {
    resource: 'projects',
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    label: 'AX-2201',
    subtitle: 'Injection mold housing',
    details: null,
    match_kind: 'exact',
    via_kind: null,
    ...overrides,
  }
}

function makeGroup(overrides: Partial<GlobalSearchGroup> = {}): GlobalSearchGroup {
  return {
    resource: 'projects',
    total: 0,
    items: [],
    ...overrides,
  }
}

function makeResponse(groups: GlobalSearchGroup[], query = 'AX-22'): GlobalSearchResponse {
  return { query, groups }
}

describe('searchStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    globalSearchMock.mockReset()
  })

  it('short-circuits an empty/whitespace query without calling the API, clearing state', async () => {
    globalSearchMock.mockResolvedValue(
      makeResponse([makeGroup({ resource: 'projects', total: 1, items: [makeHit()] })]),
    )
    const store = useSearchStore()

    await store.search('AX-22')
    expect(store.groups).toHaveLength(1)

    await store.search('   ')

    expect(globalSearchMock).toHaveBeenCalledTimes(1)
    expect(store.query).toBe('')
    expect(store.groups).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.error).toBe(false)
  })

  it('populates groups on success; visibleGroups drops empty groups and preserves order; totalHits sums totals', async () => {
    const groups = [
      makeGroup({ resource: 'products', total: 0, items: [] }),
      makeGroup({
        resource: 'projects',
        total: 2,
        items: [makeHit(), makeHit({ id: 2, label: 'AX-2202' })],
      }),
      makeGroup({ resource: 'bought-items', total: 0, items: [] }),
      makeGroup({
        resource: 'orders',
        total: 3,
        items: [makeHit({ id: 3, resource: 'orders', label: 'ORD-1' })],
      }),
    ]
    globalSearchMock.mockResolvedValue(makeResponse(groups))
    const store = useSearchStore()

    await store.search('AX-22')

    expect(store.groups).toEqual(groups)
    expect(store.visibleGroups.map((group) => group.resource)).toEqual(['projects', 'orders'])
    expect(store.totalHits).toBe(5)
    expect(store.error).toBe(false)
    expect(store.loading).toBe(false)
  })

  it('sets error on API failure; retry() re-issues the last query', async () => {
    globalSearchMock.mockRejectedValueOnce(new Error('network error'))
    const store = useSearchStore()

    await store.search('AX-22')

    expect(store.error).toBe(true)
    expect(store.loading).toBe(false)
    expect(store.groups).toEqual([])

    globalSearchMock.mockResolvedValueOnce(
      makeResponse([makeGroup({ resource: 'projects', total: 1, items: [makeHit()] })]),
    )
    await store.retry()

    expect(globalSearchMock).toHaveBeenCalledTimes(2)
    expect(globalSearchMock.mock.calls[1]?.[0]).toBe('AX-22')
    expect(store.error).toBe(false)
    expect(store.groups[0]?.total).toBe(1)
  })

  it('measures durationMs on success, and clears it on an empty query or a failure', async () => {
    globalSearchMock.mockResolvedValueOnce(
      makeResponse([makeGroup({ resource: 'projects', total: 1, items: [makeHit()] })]),
    )
    const store = useSearchStore()

    await store.search('AX-22')
    expect(store.durationMs).not.toBeNull()
    expect(store.durationMs).toBeGreaterThanOrEqual(0)

    await store.search('   ')
    expect(store.durationMs).toBeNull()

    globalSearchMock.mockResolvedValueOnce(
      makeResponse([makeGroup({ resource: 'projects', total: 1, items: [makeHit()] })]),
    )
    await store.search('AX-22')
    expect(store.durationMs).not.toBeNull()

    globalSearchMock.mockRejectedValueOnce(new Error('network error'))
    await store.search('AX-22')
    expect(store.durationMs).toBeNull()
  })

  it('discards a slower earlier response that resolves after a faster, later one', async () => {
    const slow = deferred<GlobalSearchResponse>()
    const fast = deferred<GlobalSearchResponse>()
    globalSearchMock.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)
    const store = useSearchStore()

    // Two overlapping searches, e.g. the user types further before the
    // first, slower request comes back.
    const slowCall = store.search('sl')
    const fastCall = store.search('slow')

    // The second (fast) call resolves first...
    fast.resolve(
      makeResponse(
        [makeGroup({ resource: 'projects', total: 1, items: [makeHit({ label: 'SLOW-1' })] })],
        'slow',
      ),
    )
    await fastCall
    expect(store.groups[0]?.total).toBe(1)
    expect(store.loading).toBe(false)

    // ...then the stale first call lands, and it must be discarded, not
    // overwrite the later call's result.
    slow.resolve(
      makeResponse([makeGroup({ resource: 'projects', total: 99, items: [] })], 'sl'),
    )
    await slowCall

    expect(store.groups[0]?.total).toBe(1)
    expect(store.query).toBe('slow')
    expect(store.loading).toBe(false)
  })
})

describe('searchStore invalidation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    globalSearchMock.mockReset()
  })

  it('drops a response still in flight when the query is cleared', async () => {
    const inFlight = deferred<GlobalSearchResponse>()
    globalSearchMock.mockReturnValueOnce(inFlight.promise)
    const store = useSearchStore()

    const pending = store.search('AX-22')
    expect(store.loading).toBe(true)
    await store.search('')
    expect(store.loading).toBe(false)

    inFlight.resolve(makeResponse([makeGroup({ resource: 'projects', total: 1, items: [makeHit()] })]))
    await pending

    expect(store.groups).toEqual([])
    expect(store.durationMs).toBeNull()
  })

  it('keeps the error shown while a retry is in flight', async () => {
    globalSearchMock.mockRejectedValueOnce(new Error('network error'))
    const store = useSearchStore()
    await store.search('AX-22')

    const retry = deferred<GlobalSearchResponse>()
    globalSearchMock.mockReturnValueOnce(retry.promise)
    const pending = store.retry()

    expect(store.error).toBe(true)
    retry.resolve(makeResponse([]))
    await pending
    expect(store.error).toBe(false)
  })
})
