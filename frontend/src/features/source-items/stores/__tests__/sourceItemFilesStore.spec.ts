import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { SourceItemFile, SourceItemFileCategory } from '../../types/sourceItemsResponse'

const getForItemMock = vi.fn<(itemId: number) => Promise<SourceItemFile[]>>()
const getForItemsMock = vi.fn<(itemIds: number[]) => Promise<SourceItemFile[]>>()
const uploadMock =
  vi.fn<
    (itemId: number, file: File, category: SourceItemFileCategory) => Promise<SourceItemFile>
  >()
const removeMock = vi.fn<(itemId: number, fileId: number) => Promise<void>>()

vi.mock('../../api/sourceItemFilesApi', () => ({
  getSourceItemFiles: (itemId: number) => getForItemMock(itemId),
  getSourceItemFilesForItems: (itemIds: number[]) => getForItemsMock(itemIds),
  uploadSourceItemFile: (itemId: number, file: File, category: SourceItemFileCategory) =>
    uploadMock(itemId, file, category),
  deleteSourceItemFile: (itemId: number, fileId: number) => removeMock(itemId, fileId),
}))

import { useSourceItemFilesStore } from '../sourceItemFilesStore'

function makeFile(overrides: Partial<SourceItemFile> = {}): SourceItemFile {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    source_item_id: 1,
    file_name: 'stock.jpg',
    stored_name: 'stored-stock.jpg',
    mime_type: 'image/jpeg',
    size_bytes: 2048,
    storage_path: '/files/stored-stock.jpg',
    sha256: 'deadbeef',
    category: 'mesh',
    created: '2026-07-01T00:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    ...overrides,
  }
}

// sourceItemFilesStore is a thin createFilesStore configuration (see
// core/stores/createFilesStore.spec.ts for the generic caching/coalescing
// behaviour). These tests pin down its own wiring: the bulk
// getSourceItemFilesForItems endpoint, itemIdOf keyed off source_item_id,
// and mesh as its singleton category.
describe('useSourceItemFilesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getForItemMock.mockReset()
    getForItemsMock.mockReset()
    uploadMock.mockReset()
    removeMock.mockReset()
  })

  it('getFiles/isLoading default to empty/false for an item never fetched', () => {
    const store = useSourceItemFilesStore()
    expect(store.getFiles(1)).toEqual([])
    expect(store.isLoading(1)).toBe(false)
  })

  it('fetchFiles uses the bulk endpoint, not the single-item one', async () => {
    getForItemsMock.mockResolvedValue([makeFile({ id: 1, source_item_id: 1 })])
    const store = useSourceItemFilesStore()

    await store.fetchFiles(1)

    expect(getForItemsMock).toHaveBeenCalledWith([1])
    expect(getForItemMock).not.toHaveBeenCalled()
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, source_item_id: 1 })])
  })

  it('itemIdOf buckets a file under its source_item_id', async () => {
    getForItemsMock.mockResolvedValueOnce([makeFile({ id: 9, source_item_id: 5 })])
    const store = useSourceItemFilesStore()

    await store.fetchFiles(5)

    expect(store.getFiles(5)).toHaveLength(1)
    expect(store.getFiles(6)).toEqual([])
  })

  it('coalesces same-tick fetchFiles calls into one bulk request', async () => {
    getForItemsMock.mockResolvedValue([
      makeFile({ id: 1, source_item_id: 1 }),
      makeFile({ id: 2, source_item_id: 2 }),
    ])
    const store = useSourceItemFilesStore()

    await Promise.all([store.fetchFiles(1), store.fetchFiles(2)])

    expect(getForItemsMock).toHaveBeenCalledTimes(1)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, source_item_id: 1 })])
    expect(store.getFiles(2)).toEqual([makeFile({ id: 2, source_item_id: 2 })])
  })

  it('leaves ids uncached on a failed fetch so a later render can retry', async () => {
    getForItemsMock.mockRejectedValueOnce(new Error('500'))
    const store = useSourceItemFilesStore()

    await store.fetchFiles(1)

    expect(store.isLoading(1)).toBe(false)
    expect(store.getFiles(1)).toEqual([])

    getForItemsMock.mockResolvedValueOnce([makeFile({ id: 1, source_item_id: 1 })])
    await store.fetchFiles(1)
    expect(getForItemsMock).toHaveBeenCalledTimes(2)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, source_item_id: 1 })])
  })

  it('refetchFiles bypasses the cache with a direct getSourceItemFiles call', async () => {
    getForItemsMock.mockResolvedValueOnce([makeFile({ id: 1, source_item_id: 1 })])
    getForItemMock.mockResolvedValueOnce([
      makeFile({ id: 1, source_item_id: 1 }),
      makeFile({ id: 2, source_item_id: 1 }),
    ])
    const store = useSourceItemFilesStore()
    await store.fetchFiles(1)
    expect(store.getFiles(1)).toHaveLength(1)

    await store.refetchFiles(1)

    expect(getForItemMock).toHaveBeenCalledWith(1)
    expect(store.getFiles(1)).toHaveLength(2)
    expect(store.isLoading(1)).toBe(false)
  })

  it('upload of a singleton category (mesh) replaces the existing same-category file locally', async () => {
    const oldImage = makeFile({ id: 1, source_item_id: 1, category: 'mesh' })
    const newImage = makeFile({ id: 2, source_item_id: 1, category: 'mesh' })
    getForItemsMock.mockResolvedValueOnce([oldImage])
    uploadMock.mockResolvedValueOnce(newImage)
    const store = useSourceItemFilesStore()
    await store.fetchFiles(1)

    await store.upload(1, new File(['x'], 'a.stl'), 'mesh')

    expect(uploadMock).toHaveBeenCalledWith(1, expect.any(File), 'mesh')
    expect(store.getFiles(1)).toEqual([newImage])
  })

  it('upload of a non-singleton category (pdf) appends rather than replaces', async () => {
    const existing = makeFile({ id: 1, source_item_id: 1, category: 'pdf' })
    const added = makeFile({ id: 2, source_item_id: 1, category: 'pdf' })
    getForItemsMock.mockResolvedValueOnce([existing])
    uploadMock.mockResolvedValueOnce(added)
    const store = useSourceItemFilesStore()
    await store.fetchFiles(1)

    await store.upload(1, new File(['x'], 'cert.pdf'), 'pdf')

    expect(store.getFiles(1)).toEqual([existing, added])
  })

  it('remove calls deleteSourceItemFile and drops the file from the cache', async () => {
    const file = makeFile({ id: 1, source_item_id: 1 })
    getForItemsMock.mockResolvedValueOnce([file])
    const store = useSourceItemFilesStore()
    await store.fetchFiles(1)

    await store.remove(1, 1)

    expect(removeMock).toHaveBeenCalledWith(1, 1)
    expect(store.getFiles(1)).toEqual([])
  })

  it('invalidate drops an item from the cache so the next fetchFiles re-requests it', async () => {
    getForItemsMock.mockResolvedValue([makeFile({ id: 1, source_item_id: 1 })])
    const store = useSourceItemFilesStore()
    await store.fetchFiles(1)
    expect(getForItemsMock).toHaveBeenCalledTimes(1)

    store.invalidate(1)
    expect(store.getFiles(1)).toEqual([])

    await store.fetchFiles(1)
    expect(getForItemsMock).toHaveBeenCalledTimes(2)
  })
})
