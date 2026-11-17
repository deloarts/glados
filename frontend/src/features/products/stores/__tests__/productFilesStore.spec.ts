import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { ProductFile, ProductFileCategory } from '../../types/productResponse'

const getForItemsMock = vi.fn<(productIds: number[]) => Promise<ProductFile[]>>()
const getForItemMock = vi.fn<(productId: number) => Promise<ProductFile[]>>()
const uploadMock =
  vi.fn<(productId: number, file: File, category: ProductFileCategory) => Promise<ProductFile>>()
const removeMock = vi.fn<(productId: number, fileId: number) => Promise<void>>()

vi.mock('../../api/getProductFilesForItems', () => ({
  getProductFilesForItems: (productIds: number[]) => getForItemsMock(productIds),
}))
vi.mock('../../api/getProductFiles', () => ({
  getProductFiles: (productId: number) => getForItemMock(productId),
}))
vi.mock('../../api/uploadProductFile', () => ({
  uploadProductFile: (productId: number, file: File, category: ProductFileCategory) =>
    uploadMock(productId, file, category),
}))
vi.mock('../../api/deleteProductFile', () => ({
  deleteProductFile: (productId: number, fileId: number) => removeMock(productId, fileId),
}))

import { useProductFilesStore } from '../productFilesStore'

function makeFile(overrides: Partial<ProductFile> = {}): ProductFile {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    product_id: 1,
    file_name: 'thumb.png',
    stored_name: 'stored-thumb.png',
    mime_type: 'image/png',
    size_bytes: 512,
    storage_path: '/files/stored-thumb.png',
    sha256: 'deadbeef',
    category: 'thumbnail',
    created: '2026-07-01T00:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    ...overrides,
  }
}

// productFilesStore is a thin createFilesStore configuration (see
// createFilesStore.spec.ts for the generic caching/coalescing behaviour).
// These tests pin down its own wiring: a bulk getForItems endpoint (products
// render a thumbnail per catalogue row), itemIdOf keyed off product_id, and
// SINGLETON_FILE_CATEGORIES = ['thumbnail', 'image']: a product carries at
// most one of each, while 'pdf' accumulates.
describe('useProductFilesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getForItemsMock.mockReset()
    getForItemMock.mockReset()
    uploadMock.mockReset()
    removeMock.mockReset()
  })

  it('getFiles/isLoading default to empty/false for a product never fetched', () => {
    const store = useProductFilesStore()
    expect(store.getFiles(1)).toEqual([])
    expect(store.isLoading(1)).toBe(false)
  })

  it('fetchFiles marks the product loading synchronously, then populates it via the bulk endpoint', async () => {
    getForItemsMock.mockResolvedValue([makeFile({ id: 1, product_id: 1 })])
    const store = useProductFilesStore()

    const promise = store.fetchFiles(1)
    expect(store.isLoading(1)).toBe(true)
    await promise

    expect(getForItemsMock).toHaveBeenCalledWith([1])
    expect(getForItemMock).not.toHaveBeenCalled()
    expect(store.isLoading(1)).toBe(false)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, product_id: 1 })])
  })

  it('coalesces fetchFiles calls issued in the same tick into one bulk request', async () => {
    getForItemsMock.mockResolvedValue([
      makeFile({ id: 1, product_id: 1 }),
      makeFile({ id: 2, product_id: 2 }),
    ])
    const store = useProductFilesStore()

    await Promise.all([store.fetchFiles(1), store.fetchFiles(2)])

    expect(getForItemsMock).toHaveBeenCalledTimes(1)
    expect(getForItemsMock).toHaveBeenCalledWith(expect.arrayContaining([1, 2]))
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, product_id: 1 })])
    expect(store.getFiles(2)).toEqual([makeFile({ id: 2, product_id: 2 })])
  })

  it('leaves ids uncached on a failed flush so a later render can retry', async () => {
    getForItemsMock.mockRejectedValueOnce(new Error('500'))
    const store = useProductFilesStore()

    await store.fetchFiles(1)

    expect(store.isLoading(1)).toBe(false)
    expect(store.getFiles(1)).toEqual([])

    getForItemsMock.mockResolvedValueOnce([makeFile({ id: 1, product_id: 1 })])
    await store.fetchFiles(1)
    expect(getForItemsMock).toHaveBeenCalledTimes(2)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, product_id: 1 })])
  })

  it('refetchFiles bypasses the cache with a direct getProductFiles call', async () => {
    getForItemsMock.mockResolvedValueOnce([makeFile({ id: 1, product_id: 1 })])
    getForItemMock.mockResolvedValueOnce([
      makeFile({ id: 1, product_id: 1 }),
      makeFile({ id: 2, product_id: 1, category: 'pdf' }),
    ])
    const store = useProductFilesStore()
    await store.fetchFiles(1)
    expect(store.getFiles(1)).toHaveLength(1)

    await store.refetchFiles(1)

    expect(getForItemMock).toHaveBeenCalledWith(1)
    expect(store.getFiles(1)).toHaveLength(2)
    expect(store.isLoading(1)).toBe(false)
  })

  it('upload of a singleton category (thumbnail) replaces any existing same-category file locally', async () => {
    const oldThumb = makeFile({ id: 1, product_id: 1, category: 'thumbnail' })
    const newThumb = makeFile({ id: 2, product_id: 1, category: 'thumbnail' })
    getForItemsMock.mockResolvedValueOnce([oldThumb])
    uploadMock.mockResolvedValueOnce(newThumb)
    const store = useProductFilesStore()
    await store.fetchFiles(1)
    expect(store.getFiles(1)).toEqual([oldThumb])

    await store.upload(1, new File(['x'], 'a.png'), 'thumbnail')

    expect(uploadMock).toHaveBeenCalledWith(1, expect.any(File), 'thumbnail')
    expect(store.getFiles(1)).toEqual([newThumb])
  })

  it('upload of a non-singleton category (pdf) appends rather than replaces', async () => {
    const existing = makeFile({ id: 1, product_id: 1, category: 'pdf' })
    const added = makeFile({ id: 2, product_id: 1, category: 'pdf' })
    getForItemsMock.mockResolvedValueOnce([existing])
    uploadMock.mockResolvedValueOnce(added)
    const store = useProductFilesStore()
    await store.fetchFiles(1)

    await store.upload(1, new File(['x'], 'a.pdf'), 'pdf')

    expect(store.getFiles(1)).toEqual([existing, added])
  })

  it('remove calls deleteProductFile and drops the file from the cache', async () => {
    const file = makeFile({ id: 1 })
    getForItemsMock.mockResolvedValueOnce([file])
    const store = useProductFilesStore()
    await store.fetchFiles(1)

    await store.remove(1, 1)

    expect(removeMock).toHaveBeenCalledWith(1, 1)
    expect(store.getFiles(1)).toEqual([])
  })

  it('invalidate drops a product from the cache so the next fetchFiles re-requests it', async () => {
    getForItemsMock.mockResolvedValue([makeFile({ id: 1, product_id: 1 })])
    const store = useProductFilesStore()
    await store.fetchFiles(1)
    expect(getForItemsMock).toHaveBeenCalledTimes(1)

    store.invalidate(1)
    expect(store.getFiles(1)).toEqual([])

    await store.fetchFiles(1)
    expect(getForItemsMock).toHaveBeenCalledTimes(2)
  })
})
