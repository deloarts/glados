import { describe, it, expect, vi, beforeEach } from 'vitest'
import { computed } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import { createMasterDataStore, useToggleGroupBy } from '../createMasterDataStore'

interface Thing {
  id: number
  name: string
  archived: boolean
}

interface ThingParams {
  skip?: number
  limit?: number
  search?: string
  order_by?: 'name' | 'created'
  order_dir?: 'asc' | 'desc'
  include_archived?: boolean
  name?: string
  owner_id?: number
  is_active?: boolean
  created_from?: string
  created_to?: string
}

interface ThingCreate {
  name: string
}

const listMock = vi.fn<(params?: ThingParams) => Promise<PageResponse<Thing>>>()
const createMock = vi.fn<(payload: ThingCreate) => Promise<Thing>>()
const updateMock = vi.fn<(id: number, payload: ThingCreate) => Promise<Thing>>()
const archiveMock = vi.fn<(id: number) => Promise<Thing>>()
const restoreMock = vi.fn<(id: number) => Promise<Thing>>()
const placeMock = vi.fn<(id: number, target: { after_id?: number | null }) => Promise<void>>()

const api = {
  list: listMock,
  create: createMock,
  update: updateMock,
  archive: archiveMock,
  restore: restoreMock,
  place: placeMock,
}

function thing(overrides: Partial<Thing> = {}): Thing {
  return { id: 1, name: 'Alpha', archived: false, ...overrides }
}

function page(items: Thing[], total = items.length): PageResponse<Thing> {
  return { items, total, limit: 25, skip: 0 }
}

let storeCounter = 0

function makeStore() {
  storeCounter++
  return createMasterDataStore(`masterDataTest${storeCounter}`, {
    api,
    filters: { name: 'contains', owner_id: 'equals', is_active: 'boolean' },
    dateRanges: ['created'],
    extend: ({ items }) => ({
      ...useToggleGroupBy<'owner'>(),
      liveCount: computed(() => items.value.filter((t) => !t.archived).length),
    }),
  })()
}

function setFilter(store: ReturnType<typeof makeStore>, field: string, value: unknown): void {
  const current = store.filters[field] as { matchMode?: string }
  store.filters = { ...store.filters, [field]: { value, matchMode: current.matchMode } }
}

describe('createMasterDataStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listMock.mockReset()
    createMock.mockReset()
    updateMock.mockReset()
    archiveMock.mockReset()
    restoreMock.mockReset()
    placeMock.mockReset()
  })

  it('builds one empty DataTable filter per configured field with its match mode', () => {
    const store = makeStore()

    expect(store.filters).toEqual({
      name: { value: null, matchMode: 'contains' },
      owner_id: { value: null, matchMode: 'equals' },
      is_active: { value: null, matchMode: 'equals' },
    })
    expect(store.createdFrom).toBeNull()
    expect(store.createdTo).toBeNull()
  })

  it('refresh always includes archived rows and ignores the table filters', async () => {
    listMock.mockResolvedValue(page([thing()]))
    const store = makeStore()
    store.search = 'alp'
    setFilter(store, 'name', 'x')

    await store.refresh()

    expect(listMock).toHaveBeenCalledWith({ include_archived: true })
    expect(store.items).toHaveLength(1)
    expect(store.tableItems).toEqual([])
  })

  it('refresh forwards caller params but still forces include_archived', async () => {
    listMock.mockResolvedValue(page([]))
    const store = makeStore()

    await store.refresh({ name: 'b', include_archived: false })

    expect(listMock).toHaveBeenCalledWith({ name: 'b', include_archived: true })
  })

  it('refreshTable sends search, filters, date ranges, archived, sort and paging', async () => {
    listMock.mockResolvedValue(page([thing()], 40))
    const store = makeStore()
    store.search = 'alp'
    setFilter(store, 'name', 'Al')
    setFilter(store, 'owner_id', 7)
    setFilter(store, 'is_active', false)
    store.createdFrom = new Date(2026, 0, 2)
    store.createdTo = new Date(2026, 1, 3)
    store.toggleShowArchived()
    store.setSort('name', 'desc')

    await store.refreshTable({ skip: 25, limit: 25 })

    expect(listMock).toHaveBeenCalledWith({
      search: 'alp',
      name: 'Al',
      owner_id: 7,
      is_active: false,
      created_from: '2026-01-02',
      created_to: '2026-02-03',
      include_archived: true,
      order_by: 'name',
      order_dir: 'desc',
      skip: 25,
      limit: 25,
    })
    expect(store.tableItems).toHaveLength(1)
    expect(store.total).toBe(40)
    expect(store.items).toEqual([])
  })

  it('refreshTable omits empty text and id filters', async () => {
    listMock.mockResolvedValue(page([]))
    const store = makeStore()
    setFilter(store, 'name', '')
    setFilter(store, 'owner_id', 0)

    await store.refreshTable()

    expect(listMock).toHaveBeenCalledWith({})
  })

  it('discards a table response superseded by a newer table fetch', async () => {
    let resolveSlow: (value: PageResponse<Thing>) => void = () => {}
    listMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveSlow = resolve
        }),
    )
    listMock.mockResolvedValueOnce(page([thing({ id: 2, name: 'Fresh' })]))
    const store = makeStore()

    const slow = store.refreshTable()
    await store.refreshTable()
    resolveSlow(page([thing({ id: 1, name: 'Stale' })]))
    await slow

    expect(store.tableItems.map((t) => t.name)).toEqual(['Fresh'])
  })

  it('keeps picker and table fetches independent of each other', async () => {
    let resolvePicker: (value: PageResponse<Thing>) => void = () => {}
    listMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolvePicker = resolve
        }),
    )
    listMock.mockResolvedValueOnce(page([thing({ id: 2 })]))
    const store = makeStore()

    const picker = store.refresh()
    await store.refreshTable()
    resolvePicker(page([thing({ id: 1 })]))
    await picker

    expect(store.items.map((t) => t.id)).toEqual([1])
    expect(store.tableItems.map((t) => t.id)).toEqual([2])
  })

  it('surfaces a failed fetch through error and clears loading', async () => {
    const axiosLike = Object.assign(new Error('boom'), {
      isAxiosError: true,
      response: { data: { detail: 'boom' } },
    })
    listMock.mockRejectedValue(axiosLike)
    const store = makeStore()

    await store.refreshTable()

    expect(store.error).toBe('boom')
    expect(store.loading).toBe(false)
  })

  it('hasActiveFilters reacts to search, archived, date ranges and filter values', () => {
    const store = makeStore()
    expect(store.hasActiveFilters).toBe(false)

    store.search = 'x'
    expect(store.hasActiveFilters).toBe(true)
    store.search = ''

    store.toggleShowArchived()
    expect(store.hasActiveFilters).toBe(true)
    store.toggleShowArchived()

    store.createdTo = new Date(2026, 0, 1)
    expect(store.hasActiveFilters).toBe(true)
    store.createdTo = null

    setFilter(store, 'is_active', false)
    expect(store.hasActiveFilters).toBe(true)
  })

  it('clearAll resets filters, search, archived and dates but keeps sort and grouping', () => {
    const store = makeStore()
    store.search = 'x'
    setFilter(store, 'name', 'y')
    store.toggleShowArchived()
    store.createdFrom = new Date(2026, 0, 1)
    store.setSort('created', 'desc')
    store.setGroupBy('owner')

    store.clearAll()

    expect(store.search).toBe('')
    expect(store.filters.name).toEqual({ value: null, matchMode: 'contains' })
    expect(store.showArchived).toBe(false)
    expect(store.createdFrom).toBeNull()
    expect(store.clearTrigger).toBe(1)
    expect(store.sortBy).toBe('created')
    expect(store.groupBy).toBe('owner')
  })

  it('clearSort resets to no column ascending', () => {
    const store = makeStore()
    store.setSort('name', 'desc')

    store.clearSort()

    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })

  it('create appends to items and bumps refreshTrigger', async () => {
    createMock.mockResolvedValue(thing({ id: 5, name: 'New' }))
    const store = makeStore()

    const created = await store.create({ name: 'New' })

    expect(created.id).toBe(5)
    expect(store.items.map((t) => t.id)).toEqual([5])
    expect(store.refreshTrigger).toBe(1)
  })

  it('update, archive and restore replace the row in items and bump refreshTrigger', async () => {
    listMock.mockResolvedValue(page([thing({ id: 1 }), thing({ id: 2, name: 'Beta' })]))
    updateMock.mockResolvedValue(thing({ id: 2, name: 'Beta 2' }))
    archiveMock.mockResolvedValue(thing({ id: 2, name: 'Beta 2', archived: true }))
    restoreMock.mockResolvedValue(thing({ id: 2, name: 'Beta 2', archived: false }))
    const store = makeStore()
    await store.refresh()

    await store.update(2, { name: 'Beta 2' })
    expect(store.items[1]?.name).toBe('Beta 2')

    await store.archive(2)
    expect(store.items[1]?.archived).toBe(true)
    expect(store.liveCount).toBe(1)

    await store.restore(2)
    expect(store.items[1]?.archived).toBe(false)
    expect(store.refreshTrigger).toBe(3)
    expect(updateMock).toHaveBeenCalledWith(2, { name: 'Beta 2' })
  })

  it('leaves items untouched when the updated row is not loaded', async () => {
    archiveMock.mockResolvedValue(thing({ id: 9, archived: true }))
    const store = makeStore()

    await store.archive(9)

    expect(store.items).toEqual([])
    expect(store.refreshTrigger).toBe(1)
  })

  it('toggleShowActions flips the actions column', () => {
    const store = makeStore()
    store.toggleShowActions()
    expect(store.showActions).toBe(true)
  })

  it('setGroupBy toggles off when the active grouping is picked again', () => {
    const store = makeStore()

    store.setGroupBy('owner')
    expect(store.groupBy).toBe('owner')
    store.setGroupBy('owner')
    expect(store.groupBy).toBeNull()

    store.setGroupBy('owner')
    store.clearGroupBy()
    expect(store.groupBy).toBeNull()
  })

  it('manualOrder holds only while no sort, search or filter reorders the rows', () => {
    const store = makeStore()
    expect(store.manualOrder).toBe(true)

    store.toggleShowArchived()
    expect(store.manualOrder).toBe(true)

    store.setSort('name', 'asc')
    expect(store.manualOrder).toBe(false)
    store.clearSort()

    store.search = 'alp'
    expect(store.manualOrder).toBe(false)
    store.search = ''

    setFilter(store, 'name', 'alp')
    expect(store.manualOrder).toBe(false)
  })

  it('place shows the dropped page at once and refetches even when it fails', async () => {
    const store = makeStore()
    placeMock.mockRejectedValueOnce(new Error('gone'))
    listMock.mockResolvedValue(page([]))

    const dropped = [thing({ id: 2 }), thing({ id: 1 })]
    await expect(store.place(2, { before_id: 1 }, dropped)).rejects.toThrow('gone')

    expect(placeMock).toHaveBeenCalledWith(2, { before_id: 1 })
    expect(store.tableItems.map((t) => t.id)).toEqual([2, 1])
    expect(store.refreshTrigger).toBe(1)
  })

  it('exposes no date range refs when none are configured', () => {
    storeCounter++
    const store = createMasterDataStore(`masterDataTest${storeCounter}`, {
      api,
      filters: { name: 'contains' },
    })()

    expect('createdFrom' in store).toBe(false)
  })
})

describe('createMasterDataStore getById', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listMock.mockReset()
    createMock.mockReset()
  })

  it('finds a picker row by id, and nothing for an unset or unknown id', async () => {
    listMock.mockResolvedValue(page([thing({ id: 1 }), thing({ id: 2, name: 'Beta' })]))
    const store = makeStore()
    await store.refresh()

    expect(store.getById(2)?.name).toBe('Beta')
    expect(store.getById(3)).toBeUndefined()
    expect(store.getById(null)).toBeUndefined()
    expect(store.getById(undefined)).toBeUndefined()
  })

  it('sees a row added by create', async () => {
    createMock.mockResolvedValue(thing({ id: 7, name: 'Created' }))
    const store = makeStore()
    expect(store.getById(7)).toBeUndefined()

    await store.create({ name: 'Created' })

    expect(store.getById(7)?.name).toBe('Created')
  })
})

describe('createMasterDataStore mutating and buildParams', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    createMock.mockReset()
  })

  it('mutating is true while a create is in flight and false again after a failure', async () => {
    let reject!: (e: Error) => void
    createMock.mockReturnValue(new Promise((_, r) => (reject = r)))
    const store = makeStore()

    const pending = store.create({ name: 'x' })
    expect(store.mutating).toBe(true)

    reject(new Error('422'))
    await expect(pending).rejects.toThrow('422')
    expect(store.mutating).toBe(false)
    expect(store.refreshTrigger).toBe(0)
  })

  it('buildParams returns the table params without fetching', () => {
    const store = makeStore()
    store.search = 'al'
    store.setSort('name', 'desc')

    expect(store.buildParams({ skip: 25, limit: 25 })).toEqual({
      search: 'al',
      order_by: 'name',
      order_dir: 'desc',
      skip: 25,
      limit: 25,
    })
    expect(listMock).not.toHaveBeenCalled()
  })
})

describe('createMasterDataStore tableOnly', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listMock.mockReset()
    createMock.mockReset()
  })

  function makeTableOnlyStore() {
    storeCounter++
    return createMasterDataStore(`masterDataTest${storeCounter}`, {
      api,
      filters: { name: 'contains' },
      tableOnly: true,
    })()
  }

  it('refresh sends params exactly as given and fills items and total', async () => {
    listMock.mockResolvedValue(page([thing()], 9))
    const store = makeTableOnlyStore()

    await store.refresh({ search: 'al' })

    expect(listMock).toHaveBeenCalledWith({ search: 'al' })
    expect(store.items).toEqual([thing()])
    expect(store.total).toBe(9)
  })

  it('refreshTable fetches the built params into the same list as items', async () => {
    listMock.mockResolvedValue(page([thing({ id: 2 })], 30))
    const store = makeTableOnlyStore()
    store.toggleShowArchived()

    await store.refreshTable({ skip: 0, limit: 10 })

    expect(listMock).toHaveBeenCalledWith({ include_archived: true, skip: 0, limit: 10 })
    expect(store.tableItems).toEqual([thing({ id: 2 })])
    expect(store.items).toEqual([thing({ id: 2 })])
    expect(store.total).toBe(30)
  })

  it('create leaves the current page alone and bumps refreshTrigger', async () => {
    listMock.mockResolvedValue(page([thing()]))
    createMock.mockResolvedValue(thing({ id: 5, name: 'New' }))
    const store = makeTableOnlyStore()
    await store.refresh()

    await store.create({ name: 'New' })

    expect(store.items).toEqual([thing()])
    expect(store.refreshTrigger).toBe(1)
  })
})
