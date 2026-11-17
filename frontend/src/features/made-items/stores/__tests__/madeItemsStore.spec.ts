import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from 'axios'

import type { PageResponse } from '@/core/api/types'
import type { MadeItemFilterParams, MadeItemCreateRevisionRequest } from '../../types/madeItemsRequest'
import type { MadeItemResponse, MadeItemRevisionsResponse } from '../../types/madeItemsResponse'

const getMadeItemsMock =
  vi.fn<(params?: MadeItemFilterParams) => Promise<PageResponse<MadeItemResponse>>>()
const createMadeItemMock = vi.fn<(payload: unknown) => Promise<MadeItemResponse>>()
const updateMadeItemMock = vi.fn<(id: number, payload: unknown) => Promise<MadeItemResponse>>()
const mergeMadeItemMock = vi.fn<(sourceId: number, targetId: number) => Promise<MadeItemResponse>>()
const getMadeItemRevisionsMock = vi.fn<(itemId: number) => Promise<MadeItemRevisionsResponse>>()
const createMadeItemRevisionMock =
  vi.fn<(itemId: number, payload: MadeItemCreateRevisionRequest) => Promise<MadeItemResponse>>()
const archiveMadeItemMock = vi.fn<(id: number) => Promise<MadeItemResponse>>()
const restoreMadeItemMock = vi.fn<(id: number) => Promise<MadeItemResponse>>()

vi.mock('../../api/getMadeItems', () => ({
  getMadeItems: (params?: MadeItemFilterParams) => getMadeItemsMock(params),
}))
vi.mock('../../api/createMadeItem', () => ({
  createMadeItem: (payload: unknown) => createMadeItemMock(payload),
}))
vi.mock('../../api/updateMadeItem', () => ({
  updateMadeItem: (id: number, payload: unknown) => updateMadeItemMock(id, payload),
}))
vi.mock('../../api/mergeMadeItem', () => ({
  mergeMadeItem: (sourceId: number, targetId: number) => mergeMadeItemMock(sourceId, targetId),
}))
vi.mock('../../api/getMadeItemRevisions', () => ({
  getMadeItemRevisions: (itemId: number) => getMadeItemRevisionsMock(itemId),
}))
vi.mock('../../api/createMadeItemRevision', () => ({
  createMadeItemRevision: (itemId: number, payload: MadeItemCreateRevisionRequest) =>
    createMadeItemRevisionMock(itemId, payload),
}))
vi.mock('../../api/archiveMadeItem', () => ({
  archiveMadeItem: (id: number) => archiveMadeItemMock(id),
}))
vi.mock('../../api/restoreMadeItem', () => ({
  restoreMadeItem: (id: number) => restoreMadeItemMock(id),
}))

import { useMadeItemsStore } from '../madeItemsStore'

/**
 * A promise plus its resolve, so a test can control exactly when a given
 * call settles instead of racing on real timers, mirrors the helper in
 * useSequencedFetch.spec.ts / ordersStore.spec.ts.
 */
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function makeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return { id: 1, article_name: 'Widget', ...overrides } as unknown as MadeItemResponse
}

function page(items: MadeItemResponse[], total = items.length): PageResponse<MadeItemResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('useMadeItemsStore', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  beforeEach(() => {
    setActivePinia(createPinia())
    getMadeItemsMock.mockReset()
    createMadeItemMock.mockReset()
    updateMadeItemMock.mockReset()
    mergeMadeItemMock.mockReset()
    getMadeItemRevisionsMock.mockReset()
    createMadeItemRevisionMock.mockReset()
    archiveMadeItemMock.mockReset()
    restoreMadeItemMock.mockReset()
  })

  it('refresh populates items/total from the envelope via the sequenced fetch', async () => {
    getMadeItemsMock.mockResolvedValue(page([makeItem({ id: 1 }), makeItem({ id: 2 })], 2))
    const store = useMadeItemsStore()

    const promise = store.refresh({ limit: 25 })
    expect(store.loading).toBe(true)
    await promise

    expect(getMadeItemsMock).toHaveBeenCalledWith({ limit: 25 })
    expect(store.items).toHaveLength(2)
    expect(store.total).toBe(2)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  // madeItemsStore runs refresh() through useSequencedFetch, exactly like
  // its bought-items/source-items siblings, so a rejected getMadeItems() call
  // is swallowed into `error` instead of propagating out of refresh() as an
  // unhandled promise rejection.
  it('surfaces a failed refresh through error without throwing (useSequencedFetch swallows it)', async () => {
    const axiosError = Object.assign(new Error('Request failed'), {
      isAxiosError: true,
      response: { data: { detail: 'Internal Server Error' } },
    })
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    getMadeItemsMock.mockRejectedValue(axiosError)
    const store = useMadeItemsStore()

    await store.refresh()

    expect(store.items).toEqual([])
    expect(store.error).toBe('Internal Server Error')
    expect(store.loading).toBe(false)
  })

  it('discards a slow response that resolves after a faster, later refresh (last-wins)', async () => {
    const slow = deferred<PageResponse<MadeItemResponse>>()
    const fast = deferred<PageResponse<MadeItemResponse>>()
    getMadeItemsMock.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)
    const store = useMadeItemsStore()

    // Two overlapping refreshes: e.g. a filter change firing a second
    // request before the first (broader, slower) one has come back.
    const slowCall = store.refresh({ search: 'slow' })
    const fastCall = store.refresh({ search: 'fast' })

    // The second (fast) call resolves first...
    fast.resolve(page([makeItem({ id: 2, article_name: 'Fast' })]))
    await fastCall
    expect(store.items.map((i) => i.article_name)).toEqual(['Fast'])
    expect(store.loading).toBe(false)

    // ...then the stale first call lands: it must be discarded, not
    // overwrite the later call's result.
    slow.resolve(page([makeItem({ id: 1, article_name: 'Slow' })]))
    await slowCall

    expect(store.items.map((i) => i.article_name)).toEqual(['Fast'])
    expect(store.total).toBe(1)
    expect(store.loading).toBe(false)
  })

  it('clear resets items and total', async () => {
    getMadeItemsMock.mockResolvedValue(page([makeItem()], 1))
    const store = useMadeItemsStore()
    await store.refresh()

    store.clear()

    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
  })

  it('getById finds a cached item by id', async () => {
    getMadeItemsMock.mockResolvedValue(page([makeItem({ id: 7 })], 1))
    const store = useMadeItemsStore()
    await store.refresh()

    expect(store.getById(7)?.id).toBe(7)
    expect(store.getById(999)).toBeUndefined()
  })

  it('triggerRefresh bumps refreshTrigger', () => {
    const store = useMadeItemsStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })

  it('create/update delegate to the API without mutating local state', async () => {
    const created = makeItem({ id: 42 })
    createMadeItemMock.mockResolvedValue(created)
    const updated = makeItem({ id: 1, article_name: 'Renamed' })
    updateMadeItemMock.mockResolvedValue(updated)
    const store = useMadeItemsStore()

    const createResult = await store.create({ article_name: 'New' } as never)
    const updateResult = await store.update(1, { article_name: 'Renamed' } as never)

    expect(createMadeItemMock).toHaveBeenCalledWith({ article_name: 'New' })
    expect(updateMadeItemMock).toHaveBeenCalledWith(1, { article_name: 'Renamed' })
    expect(createResult).toBe(created)
    expect(updateResult).toBe(updated)
    expect(store.items).toEqual([])
  })

  it('merge removes the source item and replaces the target item with the merge result', async () => {
    getMadeItemsMock.mockResolvedValue(
      page([makeItem({ id: 1, article_name: 'Source' }), makeItem({ id: 2, article_name: 'Target' })], 2),
    )
    const store = useMadeItemsStore()
    await store.refresh()

    const merged = makeItem({ id: 2, article_name: 'Merged' })
    mergeMadeItemMock.mockResolvedValue(merged)

    const result = await store.merge(1, 2)

    expect(mergeMadeItemMock).toHaveBeenCalledWith(1, 2)
    expect(result).toBe(merged)
    expect(store.items.map((i) => i.id)).toEqual([2])
    expect(store.items[0]).toEqual(merged)
  })

  it('archive calls the API, updates the item in place, and triggers a refetch', async () => {
    getMadeItemsMock.mockResolvedValue(
      page([makeItem({ id: 1 }), makeItem({ id: 2 })], 2),
    )
    const store = useMadeItemsStore()
    await store.refresh()
    const archived = makeItem({ id: 1, article_name: 'Widget' } as never)
    archiveMadeItemMock.mockResolvedValue(archived)
    const before = store.refreshTrigger

    const result = await store.archive(1)

    expect(archiveMadeItemMock).toHaveBeenCalledWith(1)
    expect(result).toBe(archived)
    expect(store.getById(1)).toEqual(archived)
    expect(store.refreshTrigger).toBe(before + 1)
  })

  it('restore calls the API, updates the item in place, and triggers a refetch', async () => {
    getMadeItemsMock.mockResolvedValue(page([makeItem({ id: 1 })], 1))
    const store = useMadeItemsStore()
    await store.refresh()
    const restored = makeItem({ id: 1 })
    restoreMadeItemMock.mockResolvedValue(restored)
    const before = store.refreshTrigger

    const result = await store.restore(1)

    expect(restoreMadeItemMock).toHaveBeenCalledWith(1)
    expect(result).toBe(restored)
    expect(store.getById(1)).toEqual(restored)
    expect(store.refreshTrigger).toBe(before + 1)
  })

  it('replaceItems swaps in updated records for items already present, leaving others untouched', async () => {
    getMadeItemsMock.mockResolvedValue(
      page([makeItem({ id: 1, article_name: 'A' }), makeItem({ id: 2, article_name: 'B' })], 2),
    )
    const store = useMadeItemsStore()
    await store.refresh()

    store.replaceItems([makeItem({ id: 2, article_name: 'B-updated' }), makeItem({ id: 999, article_name: 'Ghost' })])

    expect(store.items.find((i) => i.id === 1)?.article_name).toBe('A')
    expect(store.items.find((i) => i.id === 2)?.article_name).toBe('B-updated')
    expect(store.items.find((i) => i.id === 999)).toBeUndefined()
  })

  // Revision management.
  describe('getRevisions/createRevision', () => {
    function makeRevisionsResponse(
      overrides: Partial<MadeItemRevisionsResponse> = {},
    ): MadeItemRevisionsResponse {
      return {
        items: [],
        next_revision: 'B',
        next_revision_error: null,
        can_create: true,
        reason: null,
        ...overrides,
      }
    }

    it('getRevisions delegates to the API without mutating local state', async () => {
      const response = makeRevisionsResponse()
      getMadeItemRevisionsMock.mockResolvedValue(response)
      const store = useMadeItemsStore()

      const result = await store.getRevisions(1)

      expect(getMadeItemRevisionsMock).toHaveBeenCalledWith(1)
      expect(result).toBe(response)
      expect(store.items).toEqual([])
    })

    it('createRevision delegates to the API and returns the created item', async () => {
      const created = makeItem({ id: 2, revision: 'B' })
      createMadeItemRevisionMock.mockResolvedValue(created)
      const store = useMadeItemsStore()

      const payload: MadeItemCreateRevisionRequest = {
        predecessor_status: 'replaced',
        item: { article_name: 'Widget' },
      }
      const result = await store.createRevision(1, payload)

      expect(createMadeItemRevisionMock).toHaveBeenCalledWith(1, payload)
      expect(result).toBe(created)
    })

    it('createRevision patches the predecessor row in the cached list to "replaced" with the new successor link', async () => {
      getMadeItemsMock.mockResolvedValue(
        page([makeItem({ id: 1, revision: 'A', status: 'active', successor_item_id: null })], 1),
      )
      const store = useMadeItemsStore()
      await store.refresh()

      const created = makeItem({ id: 2, revision: 'B' })
      createMadeItemRevisionMock.mockResolvedValue(created)

      await store.createRevision(1, { predecessor_status: 'replaced', item: { article_name: 'Widget' } })

      const predecessor = store.items.find((i) => i.id === 1)
      expect(predecessor?.status).toBe('replaced')
      expect(predecessor?.successor_item_id).toBe(2)
    })

    it('createRevision patches the predecessor to "inactive" without a successor link', async () => {
      getMadeItemsMock.mockResolvedValue(
        page([makeItem({ id: 1, revision: 'A', status: 'active', successor_item_id: null })], 1),
      )
      const store = useMadeItemsStore()
      await store.refresh()

      createMadeItemRevisionMock.mockResolvedValue(makeItem({ id: 2, revision: 'B' }))

      await store.createRevision(1, { predecessor_status: 'inactive', item: { article_name: 'Widget' } })

      const predecessor = store.items.find((i) => i.id === 1)
      expect(predecessor?.status).toBe('inactive')
      expect(predecessor?.successor_item_id).toBeNull()
    })

    it('createRevision is a no-op on the cached list when the predecessor is not loaded', async () => {
      createMadeItemRevisionMock.mockResolvedValue(makeItem({ id: 2, revision: 'B' }))
      const store = useMadeItemsStore()

      await store.createRevision(999, { predecessor_status: 'replaced', item: { article_name: 'Widget' } })

      expect(store.items).toEqual([])
    })
  })
})
