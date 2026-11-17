import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from 'axios'

import type { PageResponse } from '@/core/api/types'
import type { BoughtItemFilterParams } from '../../types/boughtItemsRequest'
import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

const getBoughtItemsMock =
  vi.fn<(params?: BoughtItemFilterParams) => Promise<PageResponse<BoughtItemResponse>>>()
const createBoughtItemMock = vi.fn<(payload: unknown) => Promise<BoughtItemResponse>>()
const updateBoughtItemMock = vi.fn<(id: number, payload: unknown) => Promise<BoughtItemResponse>>()
const mergeBoughtItemMock =
  vi.fn<(sourceId: number, targetId: number) => Promise<BoughtItemResponse>>()
const archiveBoughtItemMock = vi.fn<(id: number) => Promise<BoughtItemResponse>>()
const restoreBoughtItemMock = vi.fn<(id: number) => Promise<BoughtItemResponse>>()

vi.mock('../../api/getBoughtItems', () => ({
  getBoughtItems: (params?: BoughtItemFilterParams) => getBoughtItemsMock(params),
}))
vi.mock('../../api/createBoughtItem', () => ({
  createBoughtItem: (payload: unknown) => createBoughtItemMock(payload),
}))
vi.mock('../../api/updateBoughtItem', () => ({
  updateBoughtItem: (id: number, payload: unknown) => updateBoughtItemMock(id, payload),
}))
vi.mock('../../api/mergeBoughtItem', () => ({
  mergeBoughtItem: (sourceId: number, targetId: number) => mergeBoughtItemMock(sourceId, targetId),
}))
vi.mock('../../api/archiveBoughtItem', () => ({
  archiveBoughtItem: (id: number) => archiveBoughtItemMock(id),
}))
vi.mock('../../api/restoreBoughtItem', () => ({
  restoreBoughtItem: (id: number) => restoreBoughtItemMock(id),
}))

import { useBoughtItemsStore } from '../boughtItemsStore'

function makeItem(overrides: Partial<BoughtItemResponse> = {}): BoughtItemResponse {
  return { id: 1, article_name: 'Widget', ...overrides } as unknown as BoughtItemResponse
}

function page(items: BoughtItemResponse[], total = items.length): PageResponse<BoughtItemResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('useBoughtItemsStore', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  beforeEach(() => {
    setActivePinia(createPinia())
    getBoughtItemsMock.mockReset()
    createBoughtItemMock.mockReset()
    updateBoughtItemMock.mockReset()
    mergeBoughtItemMock.mockReset()
    archiveBoughtItemMock.mockReset()
    restoreBoughtItemMock.mockReset()
  })

  it('refresh populates items/total from the envelope via the sequenced fetch', async () => {
    getBoughtItemsMock.mockResolvedValue(page([makeItem({ id: 1 }), makeItem({ id: 2 })], 2))
    const store = useBoughtItemsStore()

    await store.refresh({ limit: 25 })

    expect(getBoughtItemsMock).toHaveBeenCalledWith({ limit: 25 })
    expect(store.items).toHaveLength(2)
    expect(store.total).toBe(2)
    expect(store.error).toBeNull()
  })

  it('surfaces a failed refresh through error without throwing (useSequencedFetch swallows it)', async () => {
    const axiosError = Object.assign(new Error('Request failed'), {
      isAxiosError: true,
      response: { data: { detail: 'Internal Server Error' } },
    })
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    getBoughtItemsMock.mockRejectedValue(axiosError)
    const store = useBoughtItemsStore()

    await store.refresh()

    expect(store.items).toEqual([])
    expect(store.error).toBe('Internal Server Error')
  })

  it('clear resets items and total', async () => {
    getBoughtItemsMock.mockResolvedValue(page([makeItem()], 1))
    const store = useBoughtItemsStore()
    await store.refresh()

    store.clear()

    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
  })

  it('getById finds a cached item by id', async () => {
    getBoughtItemsMock.mockResolvedValue(page([makeItem({ id: 7 })], 1))
    const store = useBoughtItemsStore()
    await store.refresh()

    expect(store.getById(7)?.id).toBe(7)
    expect(store.getById(999)).toBeUndefined()
  })

  it('triggerRefresh bumps refreshTrigger', () => {
    const store = useBoughtItemsStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })

  it('create delegates to the API and returns its result without mutating local state', async () => {
    const created = makeItem({ id: 42 })
    createBoughtItemMock.mockResolvedValue(created)
    const store = useBoughtItemsStore()

    const result = await store.create({ article_name: 'New' } as never)

    expect(createBoughtItemMock).toHaveBeenCalledWith({ article_name: 'New' })
    expect(result).toBe(created)
    expect(store.items).toEqual([])
  })

  it('update delegates to the API with the item id and payload', async () => {
    const updated = makeItem({ id: 1, article_name: 'Renamed' })
    updateBoughtItemMock.mockResolvedValue(updated)
    const store = useBoughtItemsStore()

    const result = await store.update(1, { article_name: 'Renamed' } as never)

    expect(updateBoughtItemMock).toHaveBeenCalledWith(1, { article_name: 'Renamed' })
    expect(result).toBe(updated)
  })

  it('merge removes the source item and replaces the target item with the merge result', async () => {
    getBoughtItemsMock.mockResolvedValue(
      page([makeItem({ id: 1, article_name: 'Source' }), makeItem({ id: 2, article_name: 'Target' })], 2),
    )
    const store = useBoughtItemsStore()
    await store.refresh()

    const merged = makeItem({ id: 2, article_name: 'Merged' })
    mergeBoughtItemMock.mockResolvedValue(merged)

    const result = await store.merge(1, 2)

    expect(mergeBoughtItemMock).toHaveBeenCalledWith(1, 2)
    expect(result).toBe(merged)
    expect(store.items.map((i) => i.id)).toEqual([2])
    // Reactive state wraps the returned object in a Proxy, so identity
    // isn't preserved through the store; compare structurally instead.
    expect(store.items[0]).toEqual(merged)
  })

  it('merge is a no-op on local state when the target is not present in the cached list', async () => {
    getBoughtItemsMock.mockResolvedValue(page([makeItem({ id: 1 })], 1))
    const store = useBoughtItemsStore()
    await store.refresh()

    const merged = makeItem({ id: 99 })
    mergeBoughtItemMock.mockResolvedValue(merged)

    await store.merge(1, 99)

    // Source id 1 is dropped; target id 99 was never cached so nothing is inserted.
    expect(store.items).toEqual([])
  })

  it('archive calls the API, updates the item in place, and triggers a refetch', async () => {
    getBoughtItemsMock.mockResolvedValue(page([makeItem({ id: 1 }), makeItem({ id: 2 })], 2))
    const store = useBoughtItemsStore()
    await store.refresh()
    const archived = makeItem({ id: 1 })
    archiveBoughtItemMock.mockResolvedValue(archived)
    const before = store.refreshTrigger

    const result = await store.archive(1)

    expect(archiveBoughtItemMock).toHaveBeenCalledWith(1)
    expect(result).toBe(archived)
    expect(store.items.find((i) => i.id === 1)).toEqual(archived)
    expect(store.refreshTrigger).toBe(before + 1)
  })

  it('restore calls the API, updates the item in place, and triggers a refetch', async () => {
    getBoughtItemsMock.mockResolvedValue(page([makeItem({ id: 1 })], 1))
    const store = useBoughtItemsStore()
    await store.refresh()
    const restored = makeItem({ id: 1 })
    restoreBoughtItemMock.mockResolvedValue(restored)
    const before = store.refreshTrigger

    const result = await store.restore(1)

    expect(restoreBoughtItemMock).toHaveBeenCalledWith(1)
    expect(result).toBe(restored)
    expect(store.items.find((i) => i.id === 1)).toEqual(restored)
    expect(store.refreshTrigger).toBe(before + 1)
  })

  it('replaceItems swaps in updated records for items already present, leaving others untouched', async () => {
    getBoughtItemsMock.mockResolvedValue(
      page([makeItem({ id: 1, article_name: 'A' }), makeItem({ id: 2, article_name: 'B' })], 2),
    )
    const store = useBoughtItemsStore()
    await store.refresh()

    store.replaceItems([makeItem({ id: 2, article_name: 'B-updated' }), makeItem({ id: 999, article_name: 'Ghost' })])

    expect(store.items.find((i) => i.id === 1)?.article_name).toBe('A')
    expect(store.items.find((i) => i.id === 2)?.article_name).toBe('B-updated')
    expect(store.items.find((i) => i.id === 999)).toBeUndefined()
  })
})
