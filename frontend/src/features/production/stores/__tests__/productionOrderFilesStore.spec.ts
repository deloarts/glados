import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { ProductionOrderFile } from '../../types/productionOrdersResponse'

const getForItemMock = vi.fn<(orderId: number) => Promise<ProductionOrderFile[]>>()
const uploadMock =
  vi.fn<
    (orderId: number, file: File, category: 'measurement_report') => Promise<ProductionOrderFile>
  >()
const removeMock = vi.fn<(orderId: number, fileId: number) => Promise<void>>()

vi.mock('../../api/getProductionOrderFiles', () => ({
  getProductionOrderFiles: (orderId: number) => getForItemMock(orderId),
}))
vi.mock('../../api/uploadProductionOrderFile', () => ({
  uploadProductionOrderFile: (orderId: number, file: File, category: 'measurement_report') =>
    uploadMock(orderId, file, category),
}))
vi.mock('../../api/deleteProductionOrderFile', () => ({
  deleteProductionOrderFile: (orderId: number, fileId: number) => removeMock(orderId, fileId),
}))

import { useProductionOrderFilesStore } from '../productionOrderFilesStore'

function makeFile(overrides: Partial<ProductionOrderFile> = {}): ProductionOrderFile {
  return {
    id: 1,
    public_id: '44444444-4444-4444-4444-444444444444',
    production_order_id: 1,
    file_name: 'report.pdf',
    stored_name: 'stored-report.pdf',
    mime_type: 'application/pdf',
    size_bytes: 1024,
    storage_path: '/files/stored-report.pdf',
    sha256: 'deadbeef',
    category: 'measurement_report',
    created: '2026-07-01T00:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    ...overrides,
  }
}

// productionOrderFilesStore is a thin createFilesStore configuration (see
// createFilesStore.spec.ts for the generic caching/coalescing behaviour).
// These tests pin down its own wiring: no bulk getForItems (production
// orders have no bulk file endpoint), itemIdOf keyed off
// production_order_id, and an empty singletonCategories list (a completion
// can carry more than one measurement_report).
describe('useProductionOrderFilesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getForItemMock.mockReset()
    uploadMock.mockReset()
    removeMock.mockReset()
  })

  it('has no bulk endpoint configured: fetchFiles falls back to one getProductionOrderFiles call per order id', async () => {
    getForItemMock.mockImplementation((orderId: number) =>
      Promise.resolve([makeFile({ id: orderId, production_order_id: orderId })]),
    )
    const store = useProductionOrderFilesStore()

    await Promise.all([store.fetchFiles(1), store.fetchFiles(2)])

    expect(getForItemMock).toHaveBeenCalledTimes(2)
    expect(getForItemMock).toHaveBeenCalledWith(1)
    expect(getForItemMock).toHaveBeenCalledWith(2)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, production_order_id: 1 })])
    expect(store.getFiles(2)).toEqual([makeFile({ id: 2, production_order_id: 2 })])
  })

  it('itemIdOf buckets a file under its production_order_id', async () => {
    getForItemMock.mockResolvedValueOnce([makeFile({ id: 9, production_order_id: 5 })])
    const store = useProductionOrderFilesStore()

    await store.fetchFiles(5)

    expect(store.getFiles(5)).toHaveLength(1)
    expect(store.getFiles(6)).toEqual([])
  })

  it('upload appends rather than replaces: measurement_report is not a singleton category', async () => {
    const first = makeFile({ id: 1 })
    const second = makeFile({ id: 2 })
    uploadMock.mockResolvedValueOnce(first).mockResolvedValueOnce(second)
    const store = useProductionOrderFilesStore()

    await store.upload(1, new File(['x'], 'a.pdf'), 'measurement_report')
    await store.upload(1, new File(['y'], 'b.pdf'), 'measurement_report')

    expect(uploadMock).toHaveBeenCalledWith(1, expect.any(File), 'measurement_report')
    expect(store.getFiles(1)).toEqual([first, second])
  })

  it('remove calls deleteProductionOrderFile and drops the file from the cache', async () => {
    const file = makeFile({ id: 1 })
    getForItemMock.mockResolvedValueOnce([file])
    const store = useProductionOrderFilesStore()
    await store.fetchFiles(1)

    await store.remove(1, 1)

    expect(removeMock).toHaveBeenCalledWith(1, 1)
    expect(store.getFiles(1)).toEqual([])
  })
})
