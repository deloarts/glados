import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { InspectionMethodFilterParams } from '../../types/inspectionMethodRequest'
import type { InspectionMethodResponse } from '../../types/inspectionMethodResponse'

const getInspectionMethodsMock =
  vi.fn<
    (params?: InspectionMethodFilterParams) => Promise<PageResponse<InspectionMethodResponse>>
  >()

vi.mock('../../api/getInspectionMethods', () => ({
  getInspectionMethods: (params?: InspectionMethodFilterParams) =>
    getInspectionMethodsMock(params),
}))
vi.mock('../../api/createInspectionMethod', () => ({ createInspectionMethod: vi.fn<() => void>() }))
vi.mock('../../api/updateInspectionMethod', () => ({ updateInspectionMethod: vi.fn<() => void>() }))

const archiveInspectionMethodMock =
  vi.fn<(methodId: number) => Promise<InspectionMethodResponse>>()
const restoreInspectionMethodMock =
  vi.fn<(methodId: number) => Promise<InspectionMethodResponse>>()

vi.mock('../../api/archiveInspectionMethod', () => ({
  archiveInspectionMethod: (methodId: number) => archiveInspectionMethodMock(methodId),
}))
vi.mock('../../api/restoreInspectionMethod', () => ({
  restoreInspectionMethod: (methodId: number) => restoreInspectionMethodMock(methodId),
}))

import { useInspectionMethodsStore } from '../inspectionMethodsStore'

function makeInspectionMethod(
  overrides: Partial<InspectionMethodResponse> = {},
): InspectionMethodResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    name: { enGB: 'Visual Inspection' },
    description: { enGB: '' },
    label_color: '#607d8b',
    label_font_color: '#ffffff',
    default_setup_minutes: null,
    default_minutes_per_piece: null,
    requires_evidence: false,
    default_machine_id: null,
    default_machine_name: null,
    archived: false,
    creator_id: 1,
    creator: null,
    ...overrides,
  }
}

function page(
  items: InspectionMethodResponse[],
  total = items.length,
): PageResponse<InspectionMethodResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('inspectionMethodsStore pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getInspectionMethodsMock.mockReset()
    archiveInspectionMethodMock.mockReset()
    restoreInspectionMethodMock.mockReset()
  })

  it('refreshTable sends skip/limit and populates tableItems/total from the envelope', async () => {
    getInspectionMethodsMock.mockResolvedValue(page([makeInspectionMethod()], 42))
    const store = useInspectionMethodsStore()

    await store.refreshTable({ skip: 25, limit: 25 })

    expect(getInspectionMethodsMock).toHaveBeenCalledWith(
      expect.objectContaining({ skip: 25, limit: 25 }),
    )
    expect(store.tableItems).toHaveLength(1)
    expect(store.total).toBe(42)
  })

  it('threads sortBy/sortDir into refreshTable as order_by/order_dir', async () => {
    getInspectionMethodsMock.mockResolvedValue(page([]))
    const store = useInspectionMethodsStore()
    store.setSort('name', 'desc')

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getInspectionMethodsMock).toHaveBeenCalledWith(
      expect.objectContaining({ order_by: 'name', order_dir: 'desc', skip: 0, limit: 25 }),
    )
  })

  it('keeps the picker-facing refresh() unpaginated and separate from tableItems', async () => {
    getInspectionMethodsMock.mockResolvedValue(page([makeInspectionMethod({ id: 9 })], 1))
    const store = useInspectionMethodsStore()

    await store.refresh()

    expect(getInspectionMethodsMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ skip: expect.anything() }),
    )
    expect(store.items).toHaveLength(1)
    expect(store.tableItems).toHaveLength(0)
  })

  it('bumps refreshTrigger independently so the table can react to it', () => {
    const store = useInspectionMethodsStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })

  it('derives activeItems from items (via refresh), unaffected by refreshTable/tableItems', async () => {
    getInspectionMethodsMock.mockResolvedValueOnce(
      page([
        makeInspectionMethod({ id: 1, name: { enGB: 'Active Method' }, archived: false }),
        makeInspectionMethod({ id: 2, name: { enGB: 'Archived Method' }, archived: true }),
      ]),
    )
    const store = useInspectionMethodsStore()

    await store.refresh()

    expect(store.items).toHaveLength(2)
    expect(store.activeItems).toHaveLength(1)
    const [firstActive] = store.activeItems
    if (!firstActive) throw new Error('expected at least one active item')
    expect(firstActive.id).toBe(1)

    // A different (even empty) paginated result must not shrink activeItems:
    // it is derived from `items`, never from `tableItems`.
    getInspectionMethodsMock.mockResolvedValueOnce(page([]))
    await store.refreshTable({ skip: 0, limit: 25 })

    expect(store.tableItems).toHaveLength(0)
    expect(store.items).toHaveLength(2)
    expect(store.activeItems).toHaveLength(1)
    const [firstActiveAfter] = store.activeItems
    if (!firstActiveAfter) throw new Error('expected at least one active item')
    expect(firstActiveAfter.id).toBe(1)
  })

  // Referencing an already-archived inspection method is allowed. Pickers
  // built on `items` (via useArchivableOptions) need archived rows in the
  // list too, so the picker-facing refresh() always asks for them regardless
  // of the management table's own "Show archived" toggle. `activeItems`
  // above stays live-only, unaffected by this.
  it('refresh always requests include_archived, independent of the showArchived toggle', async () => {
    getInspectionMethodsMock.mockResolvedValue(
      page([
        makeInspectionMethod({ id: 1, archived: false }),
        makeInspectionMethod({ id: 2, archived: true }),
      ]),
    )
    const store = useInspectionMethodsStore()

    await store.refresh()

    expect(getInspectionMethodsMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_archived: true }),
    )
    expect(store.items).toHaveLength(2)

    getInspectionMethodsMock.mockClear()
    store.toggleShowArchived()
    await store.refresh()

    expect(getInspectionMethodsMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_archived: true }),
    )
  })

  it('showArchived starts false, toggles, feeds include_archived in buildParams, counts in hasActiveFilters, and resets on clearAll', async () => {
    getInspectionMethodsMock.mockResolvedValue(page([]))
    const store = useInspectionMethodsStore()

    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getInspectionMethodsMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ include_archived: expect.anything() }),
    )

    store.toggleShowArchived()
    expect(store.showArchived).toBe(true)
    expect(store.hasActiveFilters).toBe(true)

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getInspectionMethodsMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_archived: true }),
    )

    store.clearAll()
    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('archive calls the archive api, replaces the item in place, and triggers a refresh', async () => {
    const archived = makeInspectionMethod({ id: 1, archived: true })
    archiveInspectionMethodMock.mockResolvedValue(archived)
    getInspectionMethodsMock.mockResolvedValue(page([makeInspectionMethod({ id: 1, archived: false })]))
    const store = useInspectionMethodsStore()
    await store.refresh()
    const refreshesBefore = store.refreshTrigger

    await store.archive(1)

    expect(archiveInspectionMethodMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(archived)
    expect(store.refreshTrigger).toBe(refreshesBefore + 1)
  })

  it('restore calls the restore api, replaces the item in place, and triggers a refresh', async () => {
    const restored = makeInspectionMethod({ id: 1, archived: false })
    restoreInspectionMethodMock.mockResolvedValue(restored)
    getInspectionMethodsMock.mockResolvedValue(page([makeInspectionMethod({ id: 1, archived: true })]))
    const store = useInspectionMethodsStore()
    await store.refresh()
    const refreshesBefore = store.refreshTrigger

    await store.restore(1)

    expect(restoreInspectionMethodMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(restored)
    expect(store.refreshTrigger).toBe(refreshesBefore + 1)
  })
})
