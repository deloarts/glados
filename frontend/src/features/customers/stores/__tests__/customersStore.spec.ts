import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { CustomerFilterParams } from '../../types/customerRequest'
import type { CustomerResponse } from '../../types/customerResponse'

const getCustomersMock =
  vi.fn<(params?: CustomerFilterParams) => Promise<PageResponse<CustomerResponse>>>()

vi.mock('../../api/getCustomers', () => ({
  getCustomers: (params?: CustomerFilterParams) => getCustomersMock(params),
}))
vi.mock('../../api/createCustomer', () => ({ createCustomer: vi.fn<() => void>() }))
vi.mock('../../api/updateCustomer', () => ({ updateCustomer: vi.fn<() => void>() }))
vi.mock('../../api/archiveCustomer', () => ({ archiveCustomer: vi.fn<() => void>() }))
vi.mock('../../api/restoreCustomer', () => ({ restoreCustomer: vi.fn<() => void>() }))

import { useCustomersStore } from '../customersStore'

function makeCustomer(overrides: Partial<CustomerResponse> = {}): CustomerResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: 'Acme Metals',
    legal_name: null,
    vat_id: null,
    level: 'A',
    street: null,
    city: null,
    country: null,
    postal_code: null,
    email: null,
    phone: null,
    weblink: null,
    creator_id: 1,
    creator: null,
    ...overrides,
  }
}

function page(items: CustomerResponse[], total = items.length): PageResponse<CustomerResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('customersStore pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getCustomersMock.mockReset()
  })

  it('refreshTable sends skip/limit and populates tableItems/total from the envelope', async () => {
    getCustomersMock.mockResolvedValue(page([makeCustomer()], 42))
    const store = useCustomersStore()

    await store.refreshTable({ skip: 25, limit: 25 })

    expect(getCustomersMock).toHaveBeenCalledWith(
      expect.objectContaining({ skip: 25, limit: 25 }),
    )
    expect(store.tableItems).toHaveLength(1)
    expect(store.total).toBe(42)
  })

  it('threads sortBy/sortDir into refreshTable as order_by/order_dir', async () => {
    getCustomersMock.mockResolvedValue(page([]))
    const store = useCustomersStore()
    store.setSort('name', 'desc')

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getCustomersMock).toHaveBeenCalledWith(
      expect.objectContaining({ order_by: 'name', order_dir: 'desc', skip: 0, limit: 25 }),
    )
  })

  it('keeps the picker-facing refresh() unpaginated and separate from tableItems', async () => {
    getCustomersMock.mockResolvedValue(page([makeCustomer({ id: 9 })], 1))
    const store = useCustomersStore()

    await store.refresh()

    expect(getCustomersMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ skip: expect.anything() }),
    )
    expect(store.items).toHaveLength(1)
    expect(store.tableItems).toHaveLength(0)
  })

  it('bumps refreshTrigger independently so the table can react to it', () => {
    const store = useCustomersStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })

  // Referencing an already-archived customer is allowed: pickers built on
  // `items` (via useArchivableOptions) need archived rows in the list too,
  // so the picker-facing refresh() always asks for them regardless of the
  // management table's own "Show archived" toggle.
  it('refresh always requests include_archived, independent of the showArchived toggle', async () => {
    getCustomersMock.mockResolvedValue(
      page([makeCustomer({ id: 1, archived: false }), makeCustomer({ id: 2, archived: true })]),
    )
    const store = useCustomersStore()

    await store.refresh()

    expect(getCustomersMock).toHaveBeenCalledWith(expect.objectContaining({ include_archived: true }))
    expect(store.items).toHaveLength(2)

    getCustomersMock.mockClear()
    store.toggleShowArchived()
    await store.refresh()

    expect(getCustomersMock).toHaveBeenCalledWith(expect.objectContaining({ include_archived: true }))
  })
})

describe('customersStore archive/restore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getCustomersMock.mockReset()
  })

  it('toggleShowArchived flips state, is counted by hasActiveFilters, and clearAll resets it', () => {
    const store = useCustomersStore()

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
    const { archiveCustomer } = await import('../../api/archiveCustomer')
    const archiveMock = vi.mocked(archiveCustomer)
    const archived = makeCustomer({ id: 1, archived: true })
    archiveMock.mockResolvedValue(archived)

    getCustomersMock.mockResolvedValue(page([makeCustomer({ id: 1, archived: false })]))
    const store = useCustomersStore()
    await store.refresh()
    const refreshTriggerBefore = store.refreshTrigger

    await store.archive(1)

    expect(archiveMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(archived)
    expect(store.refreshTrigger).toBe(refreshTriggerBefore + 1)
  })

  it('restore calls the restore api, updates the item in place, and triggers a refresh', async () => {
    const { restoreCustomer } = await import('../../api/restoreCustomer')
    const restoreMock = vi.mocked(restoreCustomer)
    const restored = makeCustomer({ id: 1, archived: false })
    restoreMock.mockResolvedValue(restored)

    getCustomersMock.mockResolvedValue(page([makeCustomer({ id: 1, archived: true })]))
    const store = useCustomersStore()
    await store.refresh()
    const refreshTriggerBefore = store.refreshTrigger

    await store.restore(1)

    expect(restoreMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(restored)
    expect(store.refreshTrigger).toBe(refreshTriggerBefore + 1)
  })
})

describe('customersStore column filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getCustomersMock.mockReset()
    getCustomersMock.mockResolvedValue(page([]))
  })

  it('sends every column filter, counts it as active, and clearAll resets all of them', async () => {
    const store = useCustomersStore()
    const set = (field: string, value: unknown) => {
      store.filters[field] = { value, matchMode: 'equals' }
    }
    set('legal_name', 'Holding')
    set('level', 'B')
    set('address', 'Leeds')
    set('country', 'AT')
    set('email', 'office')
    set('creator_id', 7)
    store.createdFrom = new Date(2026, 2, 10)
    store.createdTo = new Date(2026, 2, 12)
    store.changedFrom = new Date(2026, 3, 1)
    store.changedTo = new Date(2026, 3, 2)

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getCustomersMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        legal_name: 'Holding',
        level: 'B',
        address: 'Leeds',
        country: 'AT',
        email: 'office',
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

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getCustomersMock).toHaveBeenLastCalledWith({ skip: 0, limit: 25 })
  })

  it('counts a date bound alone as an active filter', () => {
    const store = useCustomersStore()
    store.createdFrom = new Date(2026, 2, 10)
    expect(store.hasActiveFilters).toBe(true)
  })
})
