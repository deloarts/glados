import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { DataTableFilterMetaData } from 'openvue/datatable'
import type {
  MachinePoolCreateRequest,
  MachinePoolFilterParams,
  MachinePoolResponse,
  MachinePoolUpdateRequest,
} from '../../types/machinePoolsResponse'

const getMachinePoolsMock =
  vi.fn<(params?: MachinePoolFilterParams) => Promise<PageResponse<MachinePoolResponse>>>()
const createMachinePoolMock =
  vi.fn<(payload: MachinePoolCreateRequest) => Promise<MachinePoolResponse>>()
const updateMachinePoolMock =
  vi.fn<(id: number, payload: MachinePoolUpdateRequest) => Promise<MachinePoolResponse>>()
const archiveMachinePoolMock = vi.fn<(id: number) => Promise<MachinePoolResponse>>()
const restoreMachinePoolMock = vi.fn<(id: number) => Promise<MachinePoolResponse>>()

vi.mock('../../api/getMachinePools', () => ({
  getMachinePools: (params?: MachinePoolFilterParams) => getMachinePoolsMock(params),
}))
vi.mock('../../api/createMachinePool', () => ({
  createMachinePool: (payload: MachinePoolCreateRequest) => createMachinePoolMock(payload),
}))
vi.mock('../../api/updateMachinePool', () => ({
  updateMachinePool: (id: number, payload: MachinePoolUpdateRequest) =>
    updateMachinePoolMock(id, payload),
}))
vi.mock('../../api/archiveMachinePool', () => ({
  archiveMachinePool: (id: number) => archiveMachinePoolMock(id),
}))
vi.mock('../../api/restoreMachinePool', () => ({
  restoreMachinePool: (id: number) => restoreMachinePoolMock(id),
}))

import { useMachinePoolsStore } from '../machinePoolsStore'

function makePool(overrides: Partial<MachinePoolResponse> = {}): MachinePoolResponse {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    archived: false,
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    name: 'CNC pool A',
    machine_ids: [1, 2],
    machines: [],
    note: null,
    creator_id: 1,
    creator_full_name: 'Creator',
    changes: [],
    ...overrides,
  }
}

function page(items: MachinePoolResponse[], total = items.length): PageResponse<MachinePoolResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('useMachinePoolsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getMachinePoolsMock.mockReset()
    createMachinePoolMock.mockReset()
    updateMachinePoolMock.mockReset()
    archiveMachinePoolMock.mockReset()
    restoreMachinePoolMock.mockReset()
  })

  it('starts empty, not loading/mutating, with no filters/sort applied', () => {
    const store = useMachinePoolsStore()
    expect(store.loading).toBe(false)
    expect(store.mutating).toBe(false)
    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
    expect(store.refreshTrigger).toBe(0)
    expect(store.search).toBe('')
    expect(store.showActions).toBe(false)
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('refresh sends params through and populates items/total from the envelope', async () => {
    getMachinePoolsMock.mockResolvedValue(page([makePool()], 5))
    const store = useMachinePoolsStore()

    await store.refresh({ search: 'CNC' })

    expect(getMachinePoolsMock).toHaveBeenCalledWith({ search: 'CNC' })
    expect(store.items).toEqual([makePool()])
    expect(store.total).toBe(5)
    expect(store.loading).toBe(false)
  })

  it('refresh surfaces a failed request through error, leaving items empty', async () => {
    getMachinePoolsMock.mockRejectedValueOnce(new Error('network error'))
    const store = useMachinePoolsStore()

    await store.refresh()

    expect(store.loading).toBe(false)
    expect(store.items).toEqual([])
  })

  it('create calls createMachinePool, bumps refreshTrigger, and returns the created pool', async () => {
    const created = makePool({ id: 2, name: 'CNC pool B' })
    createMachinePoolMock.mockResolvedValue(created)
    const store = useMachinePoolsStore()

    const payload: MachinePoolCreateRequest = { name: 'CNC pool B', machine_ids: [3] }
    const result = await store.create(payload)

    expect(createMachinePoolMock).toHaveBeenCalledWith(payload)
    expect(result).toEqual(created)
    expect(store.refreshTrigger).toBe(1)
    expect(store.mutating).toBe(false)
  })

  it('create resets mutating and leaves refreshTrigger unchanged when the request fails', async () => {
    createMachinePoolMock.mockRejectedValueOnce(new Error('422'))
    const store = useMachinePoolsStore()

    await expect(store.create({ name: 'x', machine_ids: [] })).rejects.toThrow('422')

    expect(store.mutating).toBe(false)
    expect(store.refreshTrigger).toBe(0)
  })

  it('update calls updateMachinePool, bumps refreshTrigger, and returns the updated pool', async () => {
    const updated = makePool({ id: 1, name: 'Renamed pool' })
    updateMachinePoolMock.mockResolvedValue(updated)
    const store = useMachinePoolsStore()

    const result = await store.update(1, { name: 'Renamed pool' })

    expect(updateMachinePoolMock).toHaveBeenCalledWith(1, { name: 'Renamed pool' })
    expect(result).toEqual(updated)
    expect(store.refreshTrigger).toBe(1)
  })

  it('update resets mutating and leaves refreshTrigger unchanged when the request fails', async () => {
    updateMachinePoolMock.mockRejectedValueOnce(new Error('422'))
    const store = useMachinePoolsStore()

    await expect(store.update(1, { name: 'x' })).rejects.toThrow('422')

    expect(store.mutating).toBe(false)
    expect(store.refreshTrigger).toBe(0)
  })

  it('archive calls the archive endpoint, updates the item in place, and bumps refreshTrigger', async () => {
    getMachinePoolsMock.mockResolvedValue(page([makePool()], 1))
    const store = useMachinePoolsStore()
    await store.refresh()
    archiveMachinePoolMock.mockResolvedValue(makePool({ archived: true }))

    await store.archive(1)

    expect(archiveMachinePoolMock).toHaveBeenCalledWith(1)
    expect(store.items[0]!.archived).toBe(true)
    expect(store.refreshTrigger).toBe(1)
    expect(store.mutating).toBe(false)
  })

  it('archive resets mutating and leaves the item untouched when the request fails', async () => {
    getMachinePoolsMock.mockResolvedValue(page([makePool()], 1))
    const store = useMachinePoolsStore()
    await store.refresh()
    archiveMachinePoolMock.mockRejectedValueOnce(new Error('500'))

    await expect(store.archive(1)).rejects.toThrow('500')

    expect(store.mutating).toBe(false)
    expect(store.items[0]!.archived).toBe(false)
    expect(store.refreshTrigger).toBe(0)
  })

  it('restore calls the restore endpoint and updates the item in place', async () => {
    getMachinePoolsMock.mockResolvedValue(page([makePool({ archived: true })], 1))
    const store = useMachinePoolsStore()
    await store.refresh()
    restoreMachinePoolMock.mockResolvedValue(makePool({ archived: false }))

    await store.restore(1)

    expect(restoreMachinePoolMock).toHaveBeenCalledWith(1)
    expect(store.items[0]!.archived).toBe(false)
    expect(store.refreshTrigger).toBe(1)
  })

  it('restore resets mutating and leaves the item untouched when the request fails', async () => {
    getMachinePoolsMock.mockResolvedValue(page([makePool({ archived: true })], 1))
    const store = useMachinePoolsStore()
    await store.refresh()
    restoreMachinePoolMock.mockRejectedValueOnce(new Error('500'))

    await expect(store.restore(1)).rejects.toThrow('500')

    expect(store.mutating).toBe(false)
    expect(store.items[0]!.archived).toBe(true)
  })

  it('triggerRefresh bumps refreshTrigger without calling the API', () => {
    const store = useMachinePoolsStore()
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
    expect(getMachinePoolsMock).not.toHaveBeenCalled()
  })

  it('toggleShowActions/toggleShowArchived flip their flags, and showArchived counts as an active filter', () => {
    const store = useMachinePoolsStore()
    store.toggleShowActions()
    expect(store.showActions).toBe(true)

    store.toggleShowArchived()
    expect(store.showArchived).toBe(true)
    expect(store.hasActiveFilters).toBe(true)
  })

  it('setSort/clearSort update sortBy/sortDir', () => {
    const store = useMachinePoolsStore()
    store.setSort('name', 'desc')
    expect(store.sortBy).toBe('name')
    expect(store.sortDir).toBe('desc')

    store.clearSort()
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })

  it('clear empties items/total without touching filters', () => {
    const store = useMachinePoolsStore()
    store.items = [makePool()]
    store.total = 1

    store.clear()

    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
  })

  it('clearAll resets search and showArchived, but leaves showActions alone', () => {
    const store = useMachinePoolsStore()
    store.search = 'CNC'
    store.toggleShowArchived()
    store.toggleShowActions()

    store.clearAll()

    expect(store.search).toBe('')
    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
    expect(store.showActions).toBe(true)
  })
})

describe('useMachinePoolsStore row filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getMachinePoolsMock.mockReset()
  })

  function setFilter(
    store: ReturnType<typeof useMachinePoolsStore>,
    field: string,
    value: unknown,
  ): void {
    ;(store.filters[field] as DataTableFilterMetaData).value = value
  }

  it('buildParams maps every column filter to its backend query param', () => {
    const store = useMachinePoolsStore()
    store.setSort('name', 'asc')
    setFilter(store, 'name', 'mill')
    setFilter(store, 'machine_id', 12)
    setFilter(store, 'creator_id', 3)

    expect(store.buildParams({ skip: 0, limit: 25 })).toEqual({
      skip: 0,
      limit: 25,
      order_by: 'name',
      order_dir: 'asc',
      name: 'mill',
      machine_id: 12,
      creator_id: 3,
    })
  })

  it('buildParams leaves out filters that are not set', () => {
    const store = useMachinePoolsStore()

    expect(store.buildParams({ skip: 0, limit: 25 })).toEqual({ skip: 0, limit: 25 })
  })

  it.each(['name', 'machine_id', 'creator_id'])(
    'a value in the %s filter counts as an active filter',
    (field) => {
      const store = useMachinePoolsStore()
      expect(store.hasActiveFilters).toBe(false)

      setFilter(store, field, field.endsWith('_id') ? 5 : 'x')

      expect(store.hasActiveFilters).toBe(true)
    },
  )

  it('clearAll resets every column filter', () => {
    const store = useMachinePoolsStore()
    setFilter(store, 'name', 'mill')
    setFilter(store, 'machine_id', 12)

    store.clearAll()

    expect(store.hasActiveFilters).toBe(false)
    expect(store.buildParams()).toEqual({})
  })
})
