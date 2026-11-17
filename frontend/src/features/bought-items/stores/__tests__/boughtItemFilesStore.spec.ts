import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { BoughtItemFile, BoughtItemFileCategory } from '../../types/boughtItemsResponse'

const getForItemMock = vi.fn<(itemId: number) => Promise<BoughtItemFile[]>>()
const getForItemsMock = vi.fn<(itemIds: number[]) => Promise<BoughtItemFile[]>>()
const uploadMock =
  vi.fn<
    (itemId: number, file: File, category: BoughtItemFileCategory) => Promise<BoughtItemFile>
  >()
const removeMock = vi.fn<(itemId: number, fileId: number) => Promise<void>>()

vi.mock('../../api/boughtItemFilesApi', () => ({
  getBoughtItemFiles: (itemId: number) => getForItemMock(itemId),
  getBoughtItemFilesForItems: (itemIds: number[]) => getForItemsMock(itemIds),
  uploadBoughtItemFile: (itemId: number, file: File, category: BoughtItemFileCategory) =>
    uploadMock(itemId, file, category),
  deleteBoughtItemFile: (itemId: number, fileId: number) => removeMock(itemId, fileId),
}))

import { useBoughtItemFilesStore } from '../boughtItemFilesStore'

function makeFile(overrides: Partial<BoughtItemFile> = {}): BoughtItemFile {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    bought_item_id: 1,
    file_name: 'widget.jpg',
    stored_name: 'stored-widget.jpg',
    mime_type: 'image/jpeg',
    size_bytes: 2048,
    storage_path: '/files/stored-widget.jpg',
    sha256: 'deadbeef',
    category: 'mesh',
    created: '2026-07-01T00:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    from_pdm: false,
    ...overrides,
  }
}

// boughtItemFilesStore is a thin createFilesStore configuration (see
// core/stores/createFilesStore.spec.ts for the generic caching/coalescing
// behaviour). These tests pin down its own wiring: the bulk
// getBoughtItemFilesForItems endpoint, itemIdOf keyed off bought_item_id,
// and thumbnail/image/step/mesh as singleton categories.
describe('useBoughtItemFilesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getForItemMock.mockReset()
    getForItemsMock.mockReset()
    uploadMock.mockReset()
    removeMock.mockReset()
  })

  it('getFiles/isLoading default to empty/false for an item never fetched', () => {
    const store = useBoughtItemFilesStore()
    expect(store.getFiles(1)).toEqual([])
    expect(store.isLoading(1)).toBe(false)
  })

  it('fetchFiles uses the bulk endpoint, not the single-item one', async () => {
    getForItemsMock.mockResolvedValue([makeFile({ id: 1, bought_item_id: 1 })])
    const store = useBoughtItemFilesStore()

    await store.fetchFiles(1)

    expect(getForItemsMock).toHaveBeenCalledWith([1])
    expect(getForItemMock).not.toHaveBeenCalled()
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, bought_item_id: 1 })])
  })

  it('itemIdOf buckets a file under its bought_item_id', async () => {
    getForItemsMock.mockResolvedValueOnce([makeFile({ id: 9, bought_item_id: 5 })])
    const store = useBoughtItemFilesStore()

    await store.fetchFiles(5)

    expect(store.getFiles(5)).toHaveLength(1)
    expect(store.getFiles(6)).toEqual([])
  })

  it('coalesces same-tick fetchFiles calls into one bulk request', async () => {
    getForItemsMock.mockResolvedValue([
      makeFile({ id: 1, bought_item_id: 1 }),
      makeFile({ id: 2, bought_item_id: 2 }),
    ])
    const store = useBoughtItemFilesStore()

    await Promise.all([store.fetchFiles(1), store.fetchFiles(2)])

    expect(getForItemsMock).toHaveBeenCalledTimes(1)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, bought_item_id: 1 })])
    expect(store.getFiles(2)).toEqual([makeFile({ id: 2, bought_item_id: 2 })])
  })

  it('leaves ids uncached on a failed fetch so a later render can retry', async () => {
    getForItemsMock.mockRejectedValueOnce(new Error('500'))
    const store = useBoughtItemFilesStore()

    await store.fetchFiles(1)

    expect(store.isLoading(1)).toBe(false)
    expect(store.getFiles(1)).toEqual([])

    getForItemsMock.mockResolvedValueOnce([makeFile({ id: 1, bought_item_id: 1 })])
    await store.fetchFiles(1)
    expect(getForItemsMock).toHaveBeenCalledTimes(2)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, bought_item_id: 1 })])
  })

  it('refetchFiles bypasses the cache with a direct getBoughtItemFiles call', async () => {
    getForItemsMock.mockResolvedValueOnce([makeFile({ id: 1, bought_item_id: 1 })])
    getForItemMock.mockResolvedValueOnce([
      makeFile({ id: 1, bought_item_id: 1 }),
      makeFile({ id: 2, bought_item_id: 1 }),
    ])
    const store = useBoughtItemFilesStore()
    await store.fetchFiles(1)
    expect(store.getFiles(1)).toHaveLength(1)

    await store.refetchFiles(1)

    expect(getForItemMock).toHaveBeenCalledWith(1)
    expect(store.getFiles(1)).toHaveLength(2)
    expect(store.isLoading(1)).toBe(false)
  })

  it('upload of a singleton category (step) replaces the existing same-category file locally', async () => {
    const oldStep = makeFile({ id: 1, bought_item_id: 1, category: 'step' })
    const newStep = makeFile({ id: 2, bought_item_id: 1, category: 'step' })
    getForItemsMock.mockResolvedValueOnce([oldStep])
    uploadMock.mockResolvedValueOnce(newStep)
    const store = useBoughtItemFilesStore()
    await store.fetchFiles(1)

    await store.upload(1, new File(['x'], 'a.step'), 'step')

    expect(uploadMock).toHaveBeenCalledWith(1, expect.any(File), 'step')
    expect(store.getFiles(1)).toEqual([newStep])
  })

  it('upload of a non-singleton category (drawing) appends rather than replaces', async () => {
    const existing = makeFile({ id: 1, bought_item_id: 1, category: 'drawing' })
    const added = makeFile({ id: 2, bought_item_id: 1, category: 'drawing' })
    getForItemsMock.mockResolvedValueOnce([existing])
    uploadMock.mockResolvedValueOnce(added)
    const store = useBoughtItemFilesStore()
    await store.fetchFiles(1)

    await store.upload(1, new File(['x'], 'drawing.pdf'), 'drawing')

    expect(store.getFiles(1)).toEqual([existing, added])
  })

  it('remove calls deleteBoughtItemFile and drops the file from the cache', async () => {
    const file = makeFile({ id: 1, bought_item_id: 1 })
    getForItemsMock.mockResolvedValueOnce([file])
    const store = useBoughtItemFilesStore()
    await store.fetchFiles(1)

    await store.remove(1, 1)

    expect(removeMock).toHaveBeenCalledWith(1, 1)
    expect(store.getFiles(1)).toEqual([])
  })

  it('invalidate drops an item from the cache so the next fetchFiles re-requests it', async () => {
    getForItemsMock.mockResolvedValue([makeFile({ id: 1, bought_item_id: 1 })])
    const store = useBoughtItemFilesStore()
    await store.fetchFiles(1)
    expect(getForItemsMock).toHaveBeenCalledTimes(1)

    store.invalidate(1)
    expect(store.getFiles(1)).toEqual([])

    await store.fetchFiles(1)
    expect(getForItemsMock).toHaveBeenCalledTimes(2)
  })
})
