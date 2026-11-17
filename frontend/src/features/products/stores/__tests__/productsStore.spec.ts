import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { ProductFilterParams } from '../../types/productRequest'
import type { ProductResponse } from '../../types/productResponse'

const getProductsMock =
  vi.fn<(params?: ProductFilterParams) => Promise<PageResponse<ProductResponse>>>()

vi.mock('../../api/getProducts', () => ({
  getProducts: (params?: ProductFilterParams) => getProductsMock(params),
}))
vi.mock('../../api/createProduct', () => ({ createProduct: vi.fn<() => void>() }))
vi.mock('../../api/updateProduct', () => ({ updateProduct: vi.fn<() => void>() }))
vi.mock('../../api/archiveProduct', () => ({ archiveProduct: vi.fn<() => void>() }))
vi.mock('../../api/restoreProduct', () => ({ restoreProduct: vi.fn<() => void>() }))

import { useProductsStore } from '../productsStore'

function makeProduct(overrides: Partial<ProductResponse> = {}): ProductResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    product_number: 'PN-0001',
    customer_id: null,
    customer: null,
    description: null,
    is_active: true,
    archived: false,
    designated_user_id: 1,
    created: '2026-01-01',
    creator_id: 1,
    creator: null,
    designation: null,
    machine_type: null,
    installation_site: null,
    installation_location: null,
    planned_placing_on_market: null,
    legal_basis: null,
    plc_environment_id: null,
    contains_pneumatics: false,
    contains_hydraulics: false,
    contains_electrics: false,
    contains_robotics: false,
    ...overrides,
  }
}

function page(items: ProductResponse[], total = items.length): PageResponse<ProductResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('productsStore pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProductsMock.mockReset()
  })

  it('refreshTable sends skip/limit and populates tableItems/total from the envelope', async () => {
    getProductsMock.mockResolvedValue(page([makeProduct()], 42))
    const store = useProductsStore()

    await store.refreshTable({ skip: 25, limit: 25 })

    expect(getProductsMock).toHaveBeenCalledWith(expect.objectContaining({ skip: 25, limit: 25 }))
    expect(store.tableItems).toHaveLength(1)
    expect(store.total).toBe(42)
  })

  it('threads sortBy/sortDir into refreshTable as order_by/order_dir', async () => {
    getProductsMock.mockResolvedValue(page([]))
    const store = useProductsStore()
    store.setSort('product_number', 'desc')

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getProductsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        order_by: 'product_number',
        order_dir: 'desc',
        skip: 0,
        limit: 25,
      }),
    )
  })

  it('keeps the picker-facing refresh() unpaginated and separate from tableItems', async () => {
    getProductsMock.mockResolvedValue(page([makeProduct({ id: 9 })], 1))
    const store = useProductsStore()

    await store.refresh()

    expect(getProductsMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ skip: expect.anything() }),
    )
    expect(store.items).toHaveLength(1)
    expect(store.tableItems).toHaveLength(0)
  })

  it('bumps refreshTrigger independently so the table can react to it', () => {
    const store = useProductsStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })

  // Referencing an already-archived product is allowed; pickers built on
  // `items` (via useArchivableOptions) need archived rows in the list too,
  // so the picker-facing refresh() always asks for them regardless of the
  // management table's own "Show archived" toggle.
  it('refresh always requests include_archived, independent of the showArchived toggle', async () => {
    getProductsMock.mockResolvedValue(
      page([makeProduct({ id: 1, archived: false }), makeProduct({ id: 2, archived: true })]),
    )
    const store = useProductsStore()

    await store.refresh()

    expect(getProductsMock).toHaveBeenCalledWith(expect.objectContaining({ include_archived: true }))
    expect(store.items).toHaveLength(2)

    getProductsMock.mockClear()
    store.toggleShowArchived()
    await store.refresh()

    expect(getProductsMock).toHaveBeenCalledWith(expect.objectContaining({ include_archived: true }))
  })
})

describe('productsStore archive/restore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProductsMock.mockReset()
  })

  it('toggleShowArchived flips state, is counted by hasActiveFilters, and clearAll resets it', () => {
    const store = useProductsStore()

    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)

    store.toggleShowArchived()
    expect(store.showArchived).toBe(true)
    expect(store.hasActiveFilters).toBe(true)

    store.clearAll()
    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('archive calls the archive api, updates the item in place, and triggers a refresh', async () => {
    const { archiveProduct } = await import('../../api/archiveProduct')
    const archiveMock = vi.mocked(archiveProduct)
    const archived = makeProduct({ id: 1, archived: true })
    archiveMock.mockResolvedValue(archived)

    getProductsMock.mockResolvedValue(page([makeProduct({ id: 1, archived: false })]))
    const store = useProductsStore()
    await store.refresh()
    const refreshTriggerBefore = store.refreshTrigger

    await store.archive(1)

    expect(archiveMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(archived)
    expect(store.refreshTrigger).toBe(refreshTriggerBefore + 1)
  })

  it('restore calls the restore api, updates the item in place, and triggers a refresh', async () => {
    const { restoreProduct } = await import('../../api/restoreProduct')
    const restoreMock = vi.mocked(restoreProduct)
    const restored = makeProduct({ id: 1, archived: false })
    restoreMock.mockResolvedValue(restored)

    getProductsMock.mockResolvedValue(page([makeProduct({ id: 1, archived: true })]))
    const store = useProductsStore()
    await store.refresh()
    const refreshTriggerBefore = store.refreshTrigger

    await store.restore(1)

    expect(restoreMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(restored)
    expect(store.refreshTrigger).toBe(refreshTriggerBefore + 1)
  })
})

describe('productsStore column filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProductsMock.mockReset()
    getProductsMock.mockResolvedValue(page([]))
  })

  it('sends every column filter, counts it as active, and clearAll resets all of them', async () => {
    const store = useProductsStore()
    const set = (field: string, value: unknown) => {
      store.filters[field] = { value, matchMode: 'equals' }
    }
    set('description', 'gearbox')
    set('designated_user_id', 5)
    set('creator_id', 7)
    store.createdFrom = new Date(2026, 2, 10)
    store.createdTo = new Date(2026, 2, 12)

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getProductsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        description: 'gearbox',
        designated_user_id: 5,
        creator_id: 7,
        created_from: '2026-03-10',
        created_to: '2026-03-12',
      }),
    )
    expect(store.hasActiveFilters).toBe(true)

    store.clearAll()
    expect(store.hasActiveFilters).toBe(false)

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getProductsMock).toHaveBeenLastCalledWith({ skip: 0, limit: 25 })
  })

  it('counts a date bound alone as an active filter', () => {
    const store = useProductsStore()
    store.createdTo = new Date(2026, 2, 12)
    expect(store.hasActiveFilters).toBe(true)
  })
})
