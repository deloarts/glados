import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { FabricationMethodFilterParams } from '../../types/fabricationMethodRequest'
import type { FabricationMethodResponse } from '../../types/fabricationMethodResponse'

const getFabricationMethodsMock =
  vi.fn<
    (params?: FabricationMethodFilterParams) => Promise<PageResponse<FabricationMethodResponse>>
  >()

vi.mock('../../api/getFabricationMethods', () => ({
  getFabricationMethods: (params?: FabricationMethodFilterParams) =>
    getFabricationMethodsMock(params),
}))
vi.mock('../../api/createFabricationMethod', () => ({ createFabricationMethod: vi.fn<() => void>() }))
vi.mock('../../api/updateFabricationMethod', () => ({ updateFabricationMethod: vi.fn<() => void>() }))

const archiveFabricationMethodMock =
  vi.fn<(methodId: number) => Promise<FabricationMethodResponse>>()
const restoreFabricationMethodMock =
  vi.fn<(methodId: number) => Promise<FabricationMethodResponse>>()

vi.mock('../../api/archiveFabricationMethod', () => ({
  archiveFabricationMethod: (methodId: number) => archiveFabricationMethodMock(methodId),
}))
vi.mock('../../api/restoreFabricationMethod', () => ({
  restoreFabricationMethod: (methodId: number) => restoreFabricationMethodMock(methodId),
}))

import { useFabricationMethodsStore } from '../fabricationMethodsStore'

function makeMethod(overrides: Partial<FabricationMethodResponse> = {}): FabricationMethodResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    name: { enGB: 'CNC Milling' },
    description: { enGB: '' },
    label_color: '#ffffff',
    label_font_color: '#000000',
    requires_machine: true,
    required_external: false,
    default_supplier_id: null,
    default_for_assemblies: false,
    archived: false,
    creator_id: 1,
    creator: null,
    lead_time_days: null,
    ...overrides,
  }
}

function page(
  items: FabricationMethodResponse[],
  total = items.length,
): PageResponse<FabricationMethodResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('fabricationMethodsStore pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getFabricationMethodsMock.mockReset()
    archiveFabricationMethodMock.mockReset()
    restoreFabricationMethodMock.mockReset()
  })

  it('refreshTable sends skip/limit and populates tableItems/total from the envelope', async () => {
    getFabricationMethodsMock.mockResolvedValue(page([makeMethod()], 42))
    const store = useFabricationMethodsStore()

    await store.refreshTable({ skip: 25, limit: 25 })

    expect(getFabricationMethodsMock).toHaveBeenCalledWith(
      expect.objectContaining({ skip: 25, limit: 25 }),
    )
    expect(store.tableItems).toHaveLength(1)
    expect(store.total).toBe(42)
  })

  it('threads sortBy/sortDir into refreshTable as order_by/order_dir', async () => {
    getFabricationMethodsMock.mockResolvedValue(page([]))
    const store = useFabricationMethodsStore()
    store.setSort('name', 'desc')

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getFabricationMethodsMock).toHaveBeenCalledWith(
      expect.objectContaining({ order_by: 'name', order_dir: 'desc', skip: 0, limit: 25 }),
    )
  })

  it('keeps the picker-facing refresh() unpaginated and separate from tableItems', async () => {
    getFabricationMethodsMock.mockResolvedValue(page([makeMethod({ id: 9 })], 1))
    const store = useFabricationMethodsStore()

    await store.refresh()

    expect(getFabricationMethodsMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ skip: expect.anything() }),
    )
    expect(store.items).toHaveLength(1)
    expect(store.tableItems).toHaveLength(0)
  })

  it('bumps refreshTrigger independently so the table can react to it', () => {
    const store = useFabricationMethodsStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })

  it('activeItems derives from items (via refresh()) and is unaffected by refreshTable()/tableItems', async () => {
    getFabricationMethodsMock.mockResolvedValue(
      page([makeMethod({ id: 1, archived: false }), makeMethod({ id: 2, archived: true })]),
    )
    const store = useFabricationMethodsStore()

    await store.refresh()

    expect(store.items).toHaveLength(2)
    expect(store.activeItems).toHaveLength(1)
    const [firstActive] = store.activeItems
    if (!firstActive) throw new Error('expected at least one active item')
    expect(firstActive.id).toBe(1)

    // A completely different (even empty) paginated result must not affect
    // activeItems, since it derives from `items`, not `tableItems`.
    getFabricationMethodsMock.mockResolvedValue(page([]))
    await store.refreshTable({ skip: 0, limit: 25 })

    expect(store.tableItems).toHaveLength(0)
    expect(store.items).toHaveLength(2)
    expect(store.activeItems).toHaveLength(1)
    const [firstActiveAfter] = store.activeItems
    if (!firstActiveAfter) throw new Error('expected at least one active item')
    expect(firstActiveAfter.id).toBe(1)
  })

  // Referencing an already-archived fabrication method is allowed: pickers
  // built on `items` (via useArchivableOptions) need archived rows in the
  // list too, so the picker-facing refresh() always asks for them regardless
  // of the management table's own "Show archived" toggle. `activeItems`
  // above stays live-only, unaffected by this.
  it('refresh always requests include_archived, independent of the showArchived toggle', async () => {
    getFabricationMethodsMock.mockResolvedValue(
      page([makeMethod({ id: 1, archived: false }), makeMethod({ id: 2, archived: true })]),
    )
    const store = useFabricationMethodsStore()

    await store.refresh()

    expect(getFabricationMethodsMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_archived: true }),
    )
    expect(store.items).toHaveLength(2)

    getFabricationMethodsMock.mockClear()
    store.toggleShowArchived()
    await store.refresh()

    expect(getFabricationMethodsMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_archived: true }),
    )
  })

  it('showArchived starts false, toggles, feeds include_archived in buildParams, counts in hasActiveFilters, and resets on clearAll', async () => {
    getFabricationMethodsMock.mockResolvedValue(page([]))
    const store = useFabricationMethodsStore()

    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getFabricationMethodsMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ include_archived: expect.anything() }),
    )

    store.toggleShowArchived()
    expect(store.showArchived).toBe(true)
    expect(store.hasActiveFilters).toBe(true)

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getFabricationMethodsMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_archived: true }),
    )

    store.clearAll()
    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('archive calls the archive api, replaces the item in place, and triggers a refresh', async () => {
    const archived = makeMethod({ id: 1, archived: true })
    archiveFabricationMethodMock.mockResolvedValue(archived)
    getFabricationMethodsMock.mockResolvedValue(page([makeMethod({ id: 1, archived: false })]))
    const store = useFabricationMethodsStore()
    await store.refresh()
    const refreshesBefore = store.refreshTrigger

    await store.archive(1)

    expect(archiveFabricationMethodMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(archived)
    expect(store.refreshTrigger).toBe(refreshesBefore + 1)
  })

  it('restore calls the restore api, replaces the item in place, and triggers a refresh', async () => {
    const restored = makeMethod({ id: 1, archived: false })
    restoreFabricationMethodMock.mockResolvedValue(restored)
    getFabricationMethodsMock.mockResolvedValue(page([makeMethod({ id: 1, archived: true })]))
    const store = useFabricationMethodsStore()
    await store.refresh()
    const refreshesBefore = store.refreshTrigger

    await store.restore(1)

    expect(restoreFabricationMethodMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(restored)
    expect(store.refreshTrigger).toBe(refreshesBefore + 1)
  })
})
