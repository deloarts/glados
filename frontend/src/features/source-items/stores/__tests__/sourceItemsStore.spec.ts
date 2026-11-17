import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { SourceItemResponse } from '../../types/sourceItemsResponse'

const listMock = vi.fn<(params?: unknown) => Promise<PageResponse<SourceItemResponse>>>()
const createMock = vi.fn<(payload: unknown) => Promise<SourceItemResponse>>()
const updateMock = vi.fn<(id: number, payload: unknown) => Promise<SourceItemResponse>>()
const archiveMock = vi.fn<(id: number) => Promise<SourceItemResponse>>()
const restoreMock = vi.fn<(id: number) => Promise<SourceItemResponse>>()

vi.mock('../../api/sourceItemsApi', () => ({
  sourceItemsApi: {
    list: (params?: unknown) => listMock(params),
    create: (payload: unknown) => createMock(payload),
    update: (id: number, payload: unknown) => updateMock(id, payload),
    archive: (id: number) => archiveMock(id),
    restore: (id: number) => restoreMock(id),
  },
}))

import { useSourceItemsStore } from '../sourceItemsStore'

function makeItem(overrides: Partial<SourceItemResponse> = {}): SourceItemResponse {
  return { id: 1, type_name: 'Steel Rod', ...overrides } as unknown as SourceItemResponse
}

function page(items: SourceItemResponse[], total = items.length): PageResponse<SourceItemResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('useSourceItemsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listMock.mockReset()
    createMock.mockReset()
    updateMock.mockReset()
    archiveMock.mockReset()
    restoreMock.mockReset()
  })

  it('refresh populates items/total from the envelope via the sequenced fetch', async () => {
    listMock.mockResolvedValue(page([makeItem({ id: 1 }), makeItem({ id: 2 })], 2))
    const store = useSourceItemsStore()

    await store.refresh({ limit: 25 } as never)

    expect(listMock).toHaveBeenCalledWith({ limit: 25 })
    expect(store.items).toHaveLength(2)
    expect(store.total).toBe(2)
    expect(store.error).toBeNull()
  })

  it('clear resets items and total', async () => {
    listMock.mockResolvedValue(page([makeItem()], 1))
    const store = useSourceItemsStore()
    await store.refresh()

    store.clear()

    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
  })

  it('getById finds a cached item by id', async () => {
    listMock.mockResolvedValue(page([makeItem({ id: 7 })], 1))
    const store = useSourceItemsStore()
    await store.refresh()

    expect(store.getById(7)?.id).toBe(7)
    expect(store.getById(999)).toBeUndefined()
  })

  it('triggerRefresh bumps refreshTrigger', () => {
    const store = useSourceItemsStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })

  it('create/update delegate to sourceItemsApi without mutating local state', async () => {
    const created = makeItem({ id: 42 })
    createMock.mockResolvedValue(created)
    const updated = makeItem({ id: 1, type_name: { enGB: 'Renamed' } })
    updateMock.mockResolvedValue(updated)
    const store = useSourceItemsStore()

    const createResult = await store.create({ type_name: 'New' } as never)
    const updateResult = await store.update(1, { type_name: 'Renamed' } as never)

    expect(createMock).toHaveBeenCalledWith({ type_name: 'New' })
    expect(updateMock).toHaveBeenCalledWith(1, { type_name: 'Renamed' })
    expect(createResult).toBe(created)
    expect(updateResult).toBe(updated)
    expect(store.items).toEqual([])
  })

  // sourceItemsStore has no `merge` (unlike bought-items/made-items); it has
  // `archive`/`restore` instead (the backend has no DELETE endpoint for
  // source items, only archive/restore, same as the other 12 archivable
  // resources).
  it('archive calls the API, updates the item in place, and triggers a refetch', async () => {
    listMock.mockResolvedValue(page([makeItem({ id: 1 }), makeItem({ id: 2 })], 2))
    const store = useSourceItemsStore()
    await store.refresh()
    const archived = makeItem({ id: 1, archived: true } as never)
    archiveMock.mockResolvedValue(archived)
    const before = store.refreshTrigger

    const result = await store.archive(1)

    expect(archiveMock).toHaveBeenCalledWith(1)
    expect(result).toBe(archived)
    expect(store.getById(1)).toEqual(archived)
    expect(store.refreshTrigger).toBe(before + 1)
  })

  it('restore calls the API, updates the item in place, and triggers a refetch', async () => {
    listMock.mockResolvedValue(page([makeItem({ id: 1 })], 1))
    const store = useSourceItemsStore()
    await store.refresh()
    const restored = makeItem({ id: 1, archived: false } as never)
    restoreMock.mockResolvedValue(restored)
    const before = store.refreshTrigger

    const result = await store.restore(1)

    expect(restoreMock).toHaveBeenCalledWith(1)
    expect(result).toBe(restored)
    expect(store.getById(1)).toEqual(restored)
    expect(store.refreshTrigger).toBe(before + 1)
  })

  it('replaceItems swaps in updated records for items already present, leaving others untouched', async () => {
    listMock.mockResolvedValue(
      page([makeItem({ id: 1, type_name: { enGB: 'A' } }), makeItem({ id: 2, type_name: { enGB: 'B' } })], 2),
    )
    const store = useSourceItemsStore()
    await store.refresh()

    store.replaceItems([
      makeItem({ id: 2, type_name: { enGB: 'B-updated' } }),
      makeItem({ id: 999, type_name: { enGB: 'Ghost' } }),
    ])

    expect(store.items.find((i) => i.id === 1)?.type_name).toEqual({ enGB: 'A' })
    expect(store.items.find((i) => i.id === 2)?.type_name).toEqual({ enGB: 'B-updated' })
    expect(store.items.find((i) => i.id === 999)).toBeUndefined()
  })
})
