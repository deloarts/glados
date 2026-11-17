import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { DataTableFilterMetaData } from 'openvue/datatable'
import type {
  ProductionMachineCreateRequest,
  ProductionMachineFilterParams,
  ProductionMachineUpdateRequest,
} from '../../types/productionMachinesRequest'
import type { ProductionMachineResponse } from '../../types/productionMachinesResponse'

const getProductionMachinesMock =
  vi.fn<
    (params?: ProductionMachineFilterParams) => Promise<PageResponse<ProductionMachineResponse>>
  >()
const createProductionMachineMock =
  vi.fn<(payload: ProductionMachineCreateRequest) => Promise<ProductionMachineResponse>>()
const updateProductionMachineMock =
  vi.fn<
    (id: number, payload: ProductionMachineUpdateRequest) => Promise<ProductionMachineResponse>
  >()
const archiveProductionMachineMock = vi.fn<(id: number) => Promise<ProductionMachineResponse>>()
const restoreProductionMachineMock = vi.fn<(id: number) => Promise<ProductionMachineResponse>>()

vi.mock('../../api/getProductionMachines', () => ({
  getProductionMachines: (params?: ProductionMachineFilterParams) =>
    getProductionMachinesMock(params),
}))
vi.mock('../../api/createProductionMachine', () => ({
  createProductionMachine: (payload: ProductionMachineCreateRequest) =>
    createProductionMachineMock(payload),
}))
vi.mock('../../api/updateProductionMachine', () => ({
  updateProductionMachine: (id: number, payload: ProductionMachineUpdateRequest) =>
    updateProductionMachineMock(id, payload),
}))
vi.mock('../../api/archiveProductionMachine', () => ({
  archiveProductionMachine: (id: number) => archiveProductionMachineMock(id),
}))
vi.mock('../../api/restoreProductionMachine', () => ({
  restoreProductionMachine: (id: number) => restoreProductionMachineMock(id),
}))

import { useProductionMachinesStore } from '../productionMachinesStore'

function makeMachine(overrides: Partial<ProductionMachineResponse> = {}): ProductionMachineResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    archived: false,
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    internal_name: 'mill-01',
    vendor: 'Contoso',
    model: 'VF-2',
    fabrication_method_ids: [1],
    fabrication_methods: [],
    max_part_dimension: null,
    note: null,
    is_qa_machine: false,
    creator_id: 1,
    creator_full_name: 'Creator',
    changes: [],
    active_orders: [],
    live_order_count: 0,
    open_downtime: null,
    status: 'down',
    ...overrides,
  }
}

function page(
  items: ProductionMachineResponse[],
  total = items.length,
): PageResponse<ProductionMachineResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('useProductionMachinesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProductionMachinesMock.mockReset()
    createProductionMachineMock.mockReset()
    updateProductionMachineMock.mockReset()
    archiveProductionMachineMock.mockReset()
    restoreProductionMachineMock.mockReset()
  })

  it('starts empty, not loading/mutating, with no filters/sort/group applied', () => {
    const store = useProductionMachinesStore()
    expect(store.loading).toBe(false)
    expect(store.mutating).toBe(false)
    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
    expect(store.refreshTrigger).toBe(0)
    expect(store.search).toBe('')
    expect(store.showActions).toBe(false)
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
    expect(store.groupBy).toBeNull()
    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('refresh sends params through and populates items/total from the envelope', async () => {
    getProductionMachinesMock.mockResolvedValue(page([makeMachine()], 3))
    const store = useProductionMachinesStore()

    await store.refresh({ search: 'mill' })

    expect(getProductionMachinesMock).toHaveBeenCalledWith({ search: 'mill' })
    expect(store.items).toEqual([makeMachine()])
    expect(store.total).toBe(3)
    expect(store.loading).toBe(false)
  })

  it('refresh surfaces a failed request through error, leaving items empty', async () => {
    getProductionMachinesMock.mockRejectedValueOnce(new Error('network error'))
    const store = useProductionMachinesStore()

    await store.refresh()

    expect(store.loading).toBe(false)
    expect(store.items).toEqual([])
  })

  it('create calls createProductionMachine, bumps refreshTrigger, and returns the created machine', async () => {
    const created = makeMachine({ id: 2, internal_name: 'mill-02' })
    createProductionMachineMock.mockResolvedValue(created)
    const store = useProductionMachinesStore()

    const payload: ProductionMachineCreateRequest = {
      internal_name: 'mill-02',
      vendor: 'Contoso',
      model: 'VF-2',
      fabrication_method_ids: [1],
      is_qa_machine: false,
    }
    const result = await store.create(payload)

    expect(createProductionMachineMock).toHaveBeenCalledWith(payload)
    expect(result).toEqual(created)
    expect(store.refreshTrigger).toBe(1)
    expect(store.mutating).toBe(false)
  })

  it('create resets mutating and leaves refreshTrigger unchanged when the request fails', async () => {
    createProductionMachineMock.mockRejectedValueOnce(new Error('422'))
    const store = useProductionMachinesStore()

    await expect(
      store.create({
        internal_name: 'x',
        vendor: 'x',
        model: 'x',
        fabrication_method_ids: [],
        is_qa_machine: false,
      }),
    ).rejects.toThrow('422')

    expect(store.mutating).toBe(false)
    expect(store.refreshTrigger).toBe(0)
  })

  it('update calls updateProductionMachine, bumps refreshTrigger, and returns the updated machine', async () => {
    const updated = makeMachine({ id: 1, vendor: 'DMG' })
    updateProductionMachineMock.mockResolvedValue(updated)
    const store = useProductionMachinesStore()

    const result = await store.update(1, { vendor: 'DMG' })

    expect(updateProductionMachineMock).toHaveBeenCalledWith(1, { vendor: 'DMG' })
    expect(result).toEqual(updated)
    expect(store.refreshTrigger).toBe(1)
  })

  it('update resets mutating and leaves refreshTrigger unchanged when the request fails', async () => {
    updateProductionMachineMock.mockRejectedValueOnce(new Error('422'))
    const store = useProductionMachinesStore()

    await expect(store.update(1, { vendor: 'x' })).rejects.toThrow('422')

    expect(store.mutating).toBe(false)
    expect(store.refreshTrigger).toBe(0)
  })

  it('archive calls the archive endpoint, updates the item in place, and bumps refreshTrigger', async () => {
    getProductionMachinesMock.mockResolvedValue(page([makeMachine()], 1))
    const store = useProductionMachinesStore()
    await store.refresh()
    archiveProductionMachineMock.mockResolvedValue(makeMachine({ archived: true }))

    await store.archive(1)

    expect(archiveProductionMachineMock).toHaveBeenCalledWith(1)
    expect(store.items[0]!.archived).toBe(true)
    expect(store.refreshTrigger).toBe(1)
    expect(store.mutating).toBe(false)
  })

  it('archive resets mutating and leaves the item untouched when the request fails', async () => {
    getProductionMachinesMock.mockResolvedValue(page([makeMachine()], 1))
    const store = useProductionMachinesStore()
    await store.refresh()
    archiveProductionMachineMock.mockRejectedValueOnce(new Error('500'))

    await expect(store.archive(1)).rejects.toThrow('500')

    expect(store.mutating).toBe(false)
    expect(store.items[0]!.archived).toBe(false)
    expect(store.refreshTrigger).toBe(0)
  })

  it('restore calls the restore endpoint and updates the item in place', async () => {
    getProductionMachinesMock.mockResolvedValue(page([makeMachine({ archived: true })], 1))
    const store = useProductionMachinesStore()
    await store.refresh()
    restoreProductionMachineMock.mockResolvedValue(makeMachine({ archived: false }))

    await store.restore(1)

    expect(restoreProductionMachineMock).toHaveBeenCalledWith(1)
    expect(store.items[0]!.archived).toBe(false)
    expect(store.refreshTrigger).toBe(1)
  })

  it('restore resets mutating and leaves the item untouched when the request fails', async () => {
    getProductionMachinesMock.mockResolvedValue(page([makeMachine({ archived: true })], 1))
    const store = useProductionMachinesStore()
    await store.refresh()
    restoreProductionMachineMock.mockRejectedValueOnce(new Error('500'))

    await expect(store.restore(1)).rejects.toThrow('500')

    expect(store.mutating).toBe(false)
    expect(store.items[0]!.archived).toBe(true)
  })

  it('triggerRefresh bumps refreshTrigger without calling the API', () => {
    const store = useProductionMachinesStore()
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
    expect(getProductionMachinesMock).not.toHaveBeenCalled()
  })

  it('toggleShowActions/toggleShowArchived flip their flags, and showArchived counts as an active filter', () => {
    const store = useProductionMachinesStore()
    store.toggleShowActions()
    expect(store.showActions).toBe(true)

    store.toggleShowArchived()
    expect(store.showArchived).toBe(true)
    expect(store.hasActiveFilters).toBe(true)
  })

  it('setSort/clearSort update sortBy/sortDir', () => {
    const store = useProductionMachinesStore()
    store.setSort('vendor', 'desc')
    expect(store.sortBy).toBe('vendor')
    expect(store.sortDir).toBe('desc')

    store.clearSort()
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })

  it('setGroupBy toggles the same value off, clearGroupBy resets it', () => {
    const store = useProductionMachinesStore()
    store.setGroupBy('capability')
    expect(store.groupBy).toBe('capability')

    store.setGroupBy('capability')
    expect(store.groupBy).toBeNull()

    store.setGroupBy('capability')
    store.clearGroupBy()
    expect(store.groupBy).toBeNull()
  })

  it('clear empties items/total without touching filters', () => {
    const store = useProductionMachinesStore()
    store.items = [makeMachine()]
    store.total = 1

    store.clear()

    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
  })

  it('clearAll resets search and showArchived, but leaves showActions/groupBy alone', () => {
    const store = useProductionMachinesStore()
    store.search = 'mill'
    store.toggleShowArchived()
    store.toggleShowActions()
    store.setGroupBy('capability')

    store.clearAll()

    expect(store.search).toBe('')
    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
    expect(store.showActions).toBe(true)
    expect(store.groupBy).toBe('capability')
  })
})

describe('useProductionMachinesStore row filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProductionMachinesMock.mockReset()
  })

  function setFilter(
    store: ReturnType<typeof useProductionMachinesStore>,
    field: string,
    value: unknown,
  ): void {
    ;(store.filters[field] as DataTableFilterMetaData).value = value
  }

  it('buildParams sends only the page, sort and archived flag when no filter is set', () => {
    const store = useProductionMachinesStore()
    store.setSort('vendor', 'desc')
    store.toggleShowArchived()

    expect(store.buildParams({ skip: 25, limit: 25 })).toEqual({
      skip: 25,
      limit: 25,
      order_by: 'vendor',
      order_dir: 'desc',
      include_archived: true,
    })
  })

  it('buildParams maps every column filter to its backend query param', () => {
    const store = useProductionMachinesStore()
    store.search = 'mill'
    setFilter(store, 'internal_name', 'cnc')
    setFilter(store, 'vendor', 'contoso')
    setFilter(store, 'model', 'vf')
    setFilter(store, 'fabrication_method_id', 4)
    setFilter(store, 'creator_id', 7)

    expect(store.buildParams({ skip: 0, limit: 25 })).toEqual({
      skip: 0,
      limit: 25,
      search: 'mill',
      internal_name: 'cnc',
      vendor: 'contoso',
      model: 'vf',
      fabrication_method_id: 4,
      creator_id: 7,
    })
  })

  it('refresh passes the built params through to the API', async () => {
    getProductionMachinesMock.mockResolvedValue(page([]))
    const store = useProductionMachinesStore()
    setFilter(store, 'vendor', 'contoso')

    await store.refresh(store.buildParams({ skip: 0, limit: 10 }))

    expect(getProductionMachinesMock).toHaveBeenCalledWith({ skip: 0, limit: 10, vendor: 'contoso' })
  })

  it.each(['internal_name', 'vendor', 'model', 'fabrication_method_id', 'creator_id'])(
    'a value in the %s filter counts as an active filter',
    (field) => {
      const store = useProductionMachinesStore()
      expect(store.hasActiveFilters).toBe(false)

      setFilter(store, field, field.endsWith('_id') ? 3 : 'x')

      expect(store.hasActiveFilters).toBe(true)
    },
  )

  it('an empty text filter does not count as active', () => {
    const store = useProductionMachinesStore()
    setFilter(store, 'vendor', '')

    expect(store.hasActiveFilters).toBe(false)
    expect(store.buildParams()).toEqual({})
  })

  it('clearAll resets every column filter', () => {
    const store = useProductionMachinesStore()
    setFilter(store, 'model', 'vf')
    setFilter(store, 'creator_id', 7)

    store.clearAll()

    expect(store.hasActiveFilters).toBe(false)
    expect(store.buildParams()).toEqual({})
  })
})
