import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { SupplierFilterParams } from '../../types/supplierRequest'
import type { SupplierResponse } from '../../types/supplierResponse'

const getSuppliersMock =
  vi.fn<(params?: SupplierFilterParams) => Promise<PageResponse<SupplierResponse>>>()

vi.mock('../../api/getSuppliers', () => ({
  getSuppliers: (params?: SupplierFilterParams) => getSuppliersMock(params),
}))
vi.mock('../../api/createSupplier', () => ({ createSupplier: vi.fn<() => void>() }))
vi.mock('../../api/updateSupplier', () => ({ updateSupplier: vi.fn<() => void>() }))
vi.mock('../../api/archiveSupplier', () => ({ archiveSupplier: vi.fn<() => void>() }))
vi.mock('../../api/restoreSupplier', () => ({ restoreSupplier: vi.fn<() => void>() }))

import { useSuppliersStore } from '../suppliersStore'

function makeSupplier(overrides: Partial<SupplierResponse> = {}): SupplierResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: '2026-01-01',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: 'Acme Metals',
    legal_name: null,
    vat_id: null,
    level: 'A',
    capability_ids: [],
    capabilities: [],
    article_group_ids: [],
    article_groups: [],
    street: null,
    city: null,
    country: null,
    postal_code: null,
    email: null,
    phone: null,
    weblink: null,
    order_email: null,
    order_language: null,
    order_template: null,
    request_email: null,
    request_language: null,
    request_template: null,
    edp_type_number_first: false,
    creator_id: 1,
    creator: null,
    edp_code: null,
    external_lead_time_days: null,
    ...overrides,
  }
}

function page(items: SupplierResponse[], total = items.length): PageResponse<SupplierResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('suppliersStore pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getSuppliersMock.mockReset()
  })

  it('refreshTable sends skip/limit and populates tableItems/total from the envelope', async () => {
    getSuppliersMock.mockResolvedValue(page([makeSupplier()], 42))
    const store = useSuppliersStore()

    await store.refreshTable({ skip: 25, limit: 25 })

    expect(getSuppliersMock).toHaveBeenCalledWith(expect.objectContaining({ skip: 25, limit: 25 }))
    expect(store.tableItems).toHaveLength(1)
    expect(store.total).toBe(42)
  })

  it('threads sortBy/sortDir into refreshTable as order_by/order_dir', async () => {
    getSuppliersMock.mockResolvedValue(page([]))
    const store = useSuppliersStore()
    store.setSort('name', 'desc')

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getSuppliersMock).toHaveBeenCalledWith(
      expect.objectContaining({ order_by: 'name', order_dir: 'desc', skip: 0, limit: 25 }),
    )
  })

  it('keeps the picker-facing refresh() unpaginated and separate from tableItems', async () => {
    getSuppliersMock.mockResolvedValue(page([makeSupplier({ id: 9 })], 1))
    const store = useSuppliersStore()

    await store.refresh()

    expect(getSuppliersMock).toHaveBeenCalledWith(expect.not.objectContaining({ skip: expect.anything() }))
    expect(store.items).toHaveLength(1)
    expect(store.tableItems).toHaveLength(0)
  })

  it('bumps refreshTrigger independently so the table can react to it', () => {
    const store = useSuppliersStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })
})

describe('suppliersStore archived state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getSuppliersMock.mockReset()
  })

  it('buildParams omits include_archived by default, sends it once showArchived is toggled on, and clearAll resets it', async () => {
    getSuppliersMock.mockResolvedValue(page([]))
    const store = useSuppliersStore()

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getSuppliersMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ include_archived: expect.anything() }),
    )

    store.toggleShowArchived()
    expect(store.showArchived).toBe(true)
    expect(store.hasActiveFilters).toBe(true)

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getSuppliersMock).toHaveBeenCalledWith(expect.objectContaining({ include_archived: true }))

    store.clearAll()
    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getSuppliersMock).toHaveBeenLastCalledWith(
      expect.not.objectContaining({ include_archived: expect.anything() }),
    )
  })

  // Referencing an already-archived supplier is allowed, since pickers built on
  // `items` (via useArchivableOptions) need archived rows in the list too,
  // so the picker-facing refresh() always asks for them regardless of the
  // management table's own "Show archived" toggle.
  it('refresh always requests include_archived, independent of the showArchived toggle', async () => {
    getSuppliersMock.mockResolvedValue(
      page([makeSupplier({ id: 1, archived: false }), makeSupplier({ id: 2, archived: true })]),
    )
    const store = useSuppliersStore()

    await store.refresh()

    expect(getSuppliersMock).toHaveBeenCalledWith(expect.objectContaining({ include_archived: true }))
    expect(store.items).toHaveLength(2)

    getSuppliersMock.mockClear()
    store.toggleShowArchived()
    await store.refresh()

    expect(getSuppliersMock).toHaveBeenCalledWith(expect.objectContaining({ include_archived: true }))
  })

  // Pickers in other screens read `items`, so the management table's search,
  // column filters and sort must not narrow that list.
  it('refresh ignores the management table search, column filters and sort', async () => {
    getSuppliersMock.mockResolvedValue(page([makeSupplier()]))
    const store = useSuppliersStore()
    store.search = 'acme'
    store.filters.name = { value: 'Acme', matchMode: 'contains' }
    store.createdFrom = new Date('2026-01-01')
    store.setSort('name', 'desc')

    await store.refresh()

    expect(getSuppliersMock).toHaveBeenCalledWith({ include_archived: true })
  })
})

describe('suppliersStore archive/restore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getSuppliersMock.mockReset()
  })

  it('archive calls the archive api, updates the item in place, and triggers a refresh', async () => {
    const { archiveSupplier } = await import('../../api/archiveSupplier')
    const archiveMock = vi.mocked(archiveSupplier)
    const archived = makeSupplier({ id: 1, archived: true })
    archiveMock.mockResolvedValue(archived)

    getSuppliersMock.mockResolvedValue(page([makeSupplier({ id: 1, archived: false })]))
    const store = useSuppliersStore()
    await store.refresh()
    const refreshTriggerBefore = store.refreshTrigger

    await store.archive(1)

    expect(archiveMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(archived)
    expect(store.refreshTrigger).toBe(refreshTriggerBefore + 1)
  })

  it('restore calls the restore api, updates the item in place, and triggers a refresh', async () => {
    const { restoreSupplier } = await import('../../api/restoreSupplier')
    const restoreMock = vi.mocked(restoreSupplier)
    const restored = makeSupplier({ id: 1, archived: false })
    restoreMock.mockResolvedValue(restored)

    getSuppliersMock.mockResolvedValue(page([makeSupplier({ id: 1, archived: true })]))
    const store = useSuppliersStore()
    await store.refresh()
    const refreshTriggerBefore = store.refreshTrigger

    await store.restore(1)

    expect(restoreMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(restored)
    expect(store.refreshTrigger).toBe(refreshTriggerBefore + 1)
  })
})

describe('suppliersStore column filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getSuppliersMock.mockReset()
    getSuppliersMock.mockResolvedValue(page([]))
  })

  it('sends every column filter, counts it as active, and clearAll resets all of them', async () => {
    const store = useSuppliersStore()
    const set = (field: string, value: unknown) => {
      store.filters[field] = { value, matchMode: 'equals' }
    }
    set('legal_name', 'Holding')
    set('level', 'A')
    set('capability_id', 3)
    set('article_group_id', 4)
    set('address', 'Leeds')
    set('email', 'sales')
    set('creator_id', 7)
    store.createdFrom = new Date(2026, 2, 10)
    store.createdTo = new Date(2026, 2, 12)
    store.changedFrom = new Date(2026, 3, 1)
    store.changedTo = new Date(2026, 3, 2)

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getSuppliersMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        legal_name: 'Holding',
        level: 'A',
        capability_id: 3,
        article_group_id: 4,
        address: 'Leeds',
        email: 'sales',
        creator_id: 7,
        created_from: '2026-03-10',
        created_to: '2026-03-12',
        changed_from: '2026-04-01',
        changed_to: '2026-04-02',
      }),
    )
    expect(store.hasActiveFilters).toBe(true)

    store.clearAll()
    expect(store.hasActiveFilters).toBe(false)
    expect(store.createdFrom).toBeNull()
    expect(store.changedTo).toBeNull()

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getSuppliersMock).toHaveBeenLastCalledWith({ skip: 0, limit: 25 })
  })

  it('counts a date bound alone as an active filter', () => {
    const store = useSuppliersStore()
    store.changedTo = new Date(2026, 3, 2)
    expect(store.hasActiveFilters).toBe(true)
  })
})
