import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { OrderFile, OrderFileCategory } from '../../types/ordersResponse'

const getForItemMock = vi.fn<(orderId: number) => Promise<OrderFile[]>>()
const uploadMock = vi.fn<(orderId: number, file: File, category: OrderFileCategory) => Promise<OrderFile>>()
const removeMock = vi.fn<(orderId: number, fileId: number) => Promise<void>>()

vi.mock('../../api/getOrderFiles', () => ({
  getOrderFiles: (orderId: number) => getForItemMock(orderId),
}))
vi.mock('../../api/uploadOrderAttachment', () => ({
  uploadOrderAttachment: (orderId: number, file: File, category: OrderFileCategory) =>
    uploadMock(orderId, file, category),
}))
vi.mock('../../api/deleteOrderAttachment', () => ({
  deleteOrderAttachment: (orderId: number, fileId: number) => removeMock(orderId, fileId),
}))

import { useOrderFilesStore } from '../orderFilesStore'

function makeFile(overrides: Partial<OrderFile> = {}): OrderFile {
  return {
    id: 1,
    public_id: '33333333-3333-3333-3333-333333333333',
    order_id: 1,
    file_name: 'proposal.pdf',
    stored_name: 'stored-proposal.pdf',
    mime_type: 'application/pdf',
    size_bytes: 2048,
    storage_path: '/files/stored-proposal.pdf',
    sha256: 'cafebabe',
    category: 'proposal',
    created: '2026-07-01T00:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    delivery_id: null,
    ...overrides,
  }
}

// orderFilesStore is a thin createFilesStore configuration (see
// createFilesStore.spec.ts for the generic caching/coalescing behaviour).
// These tests pin down its own wiring: no bulk getForItems (orders have no
// bulk file endpoint, see the store's own header comment), itemIdOf keyed
// off order_id, and an empty singletonCategories list (every order file
// category accumulates, none replaces in place).
describe('useOrderFilesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getForItemMock.mockReset()
    uploadMock.mockReset()
    removeMock.mockReset()
  })

  it('getFiles/isLoading default to empty/false for an order never fetched', () => {
    const store = useOrderFilesStore()
    expect(store.getFiles(1)).toEqual([])
    expect(store.isLoading(1)).toBe(false)
  })

  it('has no bulk endpoint configured: fetchFiles falls back to one getOrderFiles call per order id', async () => {
    getForItemMock.mockImplementation((orderId: number) =>
      Promise.resolve([makeFile({ id: orderId, order_id: orderId })]),
    )
    const store = useOrderFilesStore()

    await Promise.all([store.fetchFiles(1), store.fetchFiles(2)])

    expect(getForItemMock).toHaveBeenCalledTimes(2)
    expect(getForItemMock).toHaveBeenCalledWith(1)
    expect(getForItemMock).toHaveBeenCalledWith(2)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, order_id: 1 })])
    expect(store.getFiles(2)).toEqual([makeFile({ id: 2, order_id: 2 })])
  })

  it('itemIdOf buckets a file under its order_id', async () => {
    getForItemMock.mockResolvedValueOnce([makeFile({ id: 9, order_id: 5 })])
    const store = useOrderFilesStore()

    await store.fetchFiles(5)

    expect(store.getFiles(5)).toHaveLength(1)
    expect(store.getFiles(6)).toEqual([])
  })

  it('leaves the order uncached on a failed fetch so a later render can retry', async () => {
    getForItemMock.mockRejectedValueOnce(new Error('500'))
    const store = useOrderFilesStore()

    await store.fetchFiles(1)

    expect(store.isLoading(1)).toBe(false)
    expect(store.getFiles(1)).toEqual([])

    getForItemMock.mockResolvedValueOnce([makeFile({ id: 1, order_id: 1 })])
    await store.fetchFiles(1)
    expect(getForItemMock).toHaveBeenCalledTimes(2)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, order_id: 1 })])
  })

  it('refetchFiles bypasses the cache with a direct getOrderFiles call', async () => {
    getForItemMock
      .mockResolvedValueOnce([makeFile({ id: 1, order_id: 1 })])
      .mockResolvedValueOnce([makeFile({ id: 1, order_id: 1 }), makeFile({ id: 2, order_id: 1 })])
    const store = useOrderFilesStore()
    await store.fetchFiles(1)
    expect(store.getFiles(1)).toHaveLength(1)

    await store.refetchFiles(1)

    expect(getForItemMock).toHaveBeenCalledTimes(2)
    expect(store.getFiles(1)).toHaveLength(2)
    expect(store.isLoading(1)).toBe(false)
  })

  it('upload appends rather than replaces: no category is a singleton for orders', async () => {
    const first = makeFile({ id: 1, category: 'general' })
    const second = makeFile({ id: 2, category: 'general' })
    uploadMock.mockResolvedValueOnce(first).mockResolvedValueOnce(second)
    const store = useOrderFilesStore()

    await store.upload(1, new File(['x'], 'a.pdf'), 'general')
    await store.upload(1, new File(['y'], 'b.pdf'), 'general')

    expect(uploadMock).toHaveBeenCalledWith(1, expect.any(File), 'general')
    expect(store.getFiles(1)).toEqual([first, second])
  })

  it('remove calls deleteOrderAttachment and drops the file from the cache', async () => {
    const file = makeFile({ id: 1 })
    getForItemMock.mockResolvedValueOnce([file])
    const store = useOrderFilesStore()
    await store.fetchFiles(1)

    await store.remove(1, 1)

    expect(removeMock).toHaveBeenCalledWith(1, 1)
    expect(store.getFiles(1)).toEqual([])
  })

  it('invalidate drops an order from the cache so the next fetchFiles re-requests it', async () => {
    getForItemMock.mockResolvedValue([makeFile({ id: 1, order_id: 1 })])
    const store = useOrderFilesStore()
    await store.fetchFiles(1)
    expect(getForItemMock).toHaveBeenCalledTimes(1)

    store.invalidate(1)
    expect(store.getFiles(1)).toEqual([])

    await store.fetchFiles(1)
    expect(getForItemMock).toHaveBeenCalledTimes(2)
  })
})
