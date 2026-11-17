import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { MadeItemFile, MadeItemFileCategory } from '../../types/madeItemsResponse'

const getForItemsMock = vi.fn<(itemIds: number[]) => Promise<MadeItemFile[]>>()
const getForItemMock = vi.fn<(itemId: number) => Promise<MadeItemFile[]>>()
const uploadMock =
  vi.fn<(itemId: number, file: File, category: MadeItemFileCategory) => Promise<MadeItemFile>>()
const removeMock = vi.fn<(itemId: number, fileId: number) => Promise<void>>()

vi.mock('../../api/madeItemFilesApi', () => ({
  getMadeItemFilesForItems: (itemIds: number[]) => getForItemsMock(itemIds),
  getMadeItemFiles: (itemId: number) => getForItemMock(itemId),
  uploadMadeItemFile: (itemId: number, file: File, category: MadeItemFileCategory) =>
    uploadMock(itemId, file, category),
  deleteMadeItemFile: (itemId: number, fileId: number) => removeMock(itemId, fileId),
}))

import { useMadeItemFilesStore } from '../madeItemFilesStore'

function makeFile(overrides: Partial<MadeItemFile> = {}): MadeItemFile {
  return {
    id: 1,
    public_id: '55555555-5555-5555-5555-555555555555',
    made_item_id: 1,
    file_name: 'part.step',
    stored_name: 'stored-part.step',
    mime_type: 'application/octet-stream',
    size_bytes: 2048,
    storage_path: '/files/stored-part.step',
    sha256: 'deadbeef',
    category: 'step',
    created: '2026-07-01T00:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    from_pdm: false,
    ...overrides,
  }
}

// madeItemFilesStore is a thin createFilesStore configuration (see
// createFilesStore.spec.ts for the generic caching/coalescing/error
// behaviour). These tests pin down its own wiring: the bulk getForItems
// endpoint (made items, unlike production orders, have one), itemIdOf
// keyed off made_item_id, and singletonCategories covering every category
// except 'pdf' (a made item can carry more than one PDF, but only one
// current thumbnail/step/mesh/drawing/dxf/image).
describe('useMadeItemFilesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getForItemsMock.mockReset()
    getForItemMock.mockReset()
    uploadMock.mockReset()
    removeMock.mockReset()
  })

  it('starts with no cached files and nothing loading', () => {
    const store = useMadeItemFilesStore()
    expect(store.getFiles(1)).toEqual([])
    expect(store.isLoading(1)).toBe(false)
  })

  it('coalesces concurrent fetchFiles calls into one bulk getMadeItemFilesForItems request', async () => {
    getForItemsMock.mockResolvedValue([
      makeFile({ id: 1, made_item_id: 1 }),
      makeFile({ id: 2, made_item_id: 2 }),
    ])
    const store = useMadeItemFilesStore()

    await Promise.all([store.fetchFiles(1), store.fetchFiles(2)])

    expect(getForItemsMock).toHaveBeenCalledTimes(1)
    expect(getForItemsMock).toHaveBeenCalledWith([1, 2])
    expect(getForItemMock).not.toHaveBeenCalled()
  })

  it('itemIdOf buckets each returned file under its made_item_id', async () => {
    getForItemsMock.mockResolvedValue([makeFile({ id: 9, made_item_id: 5 })])
    const store = useMadeItemFilesStore()

    await store.fetchFiles(5)

    expect(store.getFiles(5)).toHaveLength(1)
    expect(store.getFiles(6)).toEqual([])
  })

  it('caches an item with no files as an empty list rather than re-fetching it', async () => {
    getForItemsMock.mockResolvedValue([])
    const store = useMadeItemFilesStore()

    await store.fetchFiles(1)
    expect(store.getFiles(1)).toEqual([])

    await store.fetchFiles(1)
    expect(getForItemsMock).toHaveBeenCalledTimes(1)
  })

  it('sets isLoading while the bulk fetch is in flight', async () => {
    let resolveFetch!: (files: MadeItemFile[]) => void
    getForItemsMock.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve
      }),
    )
    const store = useMadeItemFilesStore()

    const promise = store.fetchFiles(1)
    expect(store.isLoading(1)).toBe(true)

    resolveFetch([makeFile({ id: 1, made_item_id: 1 })])
    await promise

    expect(store.isLoading(1)).toBe(false)
  })

  it('upload replaces the existing file for a singleton category (mesh)', async () => {
    const first = makeFile({ id: 1, category: 'mesh' })
    const second = makeFile({ id: 2, category: 'mesh' })
    uploadMock.mockResolvedValueOnce(first).mockResolvedValueOnce(second)
    const store = useMadeItemFilesStore()

    await store.upload(1, new File(['x'], 'a.stl'), 'mesh')
    await store.upload(1, new File(['y'], 'b.stl'), 'mesh')

    expect(store.getFiles(1)).toEqual([second])
  })

  it('upload appends rather than replaces for a non-singleton category (pdf)', async () => {
    const first = makeFile({ id: 1, category: 'pdf' })
    const second = makeFile({ id: 2, category: 'pdf' })
    uploadMock.mockResolvedValueOnce(first).mockResolvedValueOnce(second)
    const store = useMadeItemFilesStore()

    await store.upload(1, new File(['x'], 'a.pdf'), 'pdf')
    await store.upload(1, new File(['y'], 'b.pdf'), 'pdf')

    expect(uploadMock).toHaveBeenCalledWith(1, expect.any(File), 'pdf')
    expect(store.getFiles(1)).toEqual([first, second])
  })

  it('remove calls deleteMadeItemFile and drops the file from the cache', async () => {
    const file = makeFile({ id: 1 })
    getForItemsMock.mockResolvedValueOnce([file])
    const store = useMadeItemFilesStore()
    await store.fetchFiles(1)

    await store.remove(1, 1)

    expect(removeMock).toHaveBeenCalledWith(1, 1)
    expect(store.getFiles(1)).toEqual([])
  })

  it('refetchFiles bypasses the cache via getMadeItemFiles (not the bulk endpoint)', async () => {
    getForItemsMock.mockResolvedValueOnce([makeFile({ id: 1 })])
    const store = useMadeItemFilesStore()
    await store.fetchFiles(1)

    getForItemMock.mockResolvedValueOnce([makeFile({ id: 1 }), makeFile({ id: 2 })])
    await store.refetchFiles(1)

    expect(getForItemMock).toHaveBeenCalledWith(1)
    expect(store.getFiles(1)).toHaveLength(2)
  })

  it('invalidate drops the cached entry so a later fetchFiles re-fetches it', async () => {
    getForItemsMock.mockResolvedValue([makeFile({ id: 1 })])
    const store = useMadeItemFilesStore()
    await store.fetchFiles(1)
    expect(getForItemsMock).toHaveBeenCalledTimes(1)

    store.invalidate(1)
    await store.fetchFiles(1)

    expect(getForItemsMock).toHaveBeenCalledTimes(2)
  })

  it('a failed bulk fetch leaves the item uncached and loading false, so a later call retries', async () => {
    getForItemsMock.mockRejectedValueOnce(new Error('network error'))
    const store = useMadeItemFilesStore()

    await store.fetchFiles(1)

    expect(store.isLoading(1)).toBe(false)
    expect(store.getFiles(1)).toEqual([])

    getForItemsMock.mockResolvedValueOnce([makeFile({ id: 1 })])
    await store.fetchFiles(1)
    expect(store.getFiles(1)).toHaveLength(1)
  })

  it('a failed refetchFiles rejects and still resets isLoading', async () => {
    getForItemMock.mockRejectedValueOnce(new Error('network error'))
    const store = useMadeItemFilesStore()

    await expect(store.refetchFiles(1)).rejects.toThrow('network error')

    expect(store.isLoading(1)).toBe(false)
  })
})
