import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { SourceItemTypeFilterParams } from '../../types/sourceItemTypeRequest'
import type { SourceItemTypeResponse } from '../../types/sourceItemTypeResponse'

const getSourceItemTypesMock =
  vi.fn<(params?: SourceItemTypeFilterParams) => Promise<PageResponse<SourceItemTypeResponse>>>()

vi.mock('../../api/getSourceItemTypes', () => ({
  getSourceItemTypes: (params?: SourceItemTypeFilterParams) => getSourceItemTypesMock(params),
}))
vi.mock('../../api/createSourceItemType', () => ({ createSourceItemType: vi.fn<() => void>() }))
vi.mock('../../api/updateSourceItemType', () => ({ updateSourceItemType: vi.fn<() => void>() }))

const archiveSourceItemTypeMock =
  vi.fn<(typeId: number) => Promise<SourceItemTypeResponse>>()
const restoreSourceItemTypeMock =
  vi.fn<(typeId: number) => Promise<SourceItemTypeResponse>>()

vi.mock('../../api/archiveSourceItemType', () => ({
  archiveSourceItemType: (typeId: number) => archiveSourceItemTypeMock(typeId),
}))
vi.mock('../../api/restoreSourceItemType', () => ({
  restoreSourceItemType: (typeId: number) => restoreSourceItemTypeMock(typeId),
}))

import { useSourceItemTypesStore } from '../sourceItemTypesStore'

function makeSourceItemType(
  overrides: Partial<SourceItemTypeResponse> = {},
): SourceItemTypeResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: { enGB: 'Raw Steel' },
    label_color: '#ffffff',
    label_font_color: '#000000',
    description: { enGB: 'Raw steel stock' },
    creator_id: 1,
    creator: null,
    ...overrides,
  }
}

function page(
  items: SourceItemTypeResponse[],
  total = items.length,
): PageResponse<SourceItemTypeResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('sourceItemTypesStore pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getSourceItemTypesMock.mockReset()
    archiveSourceItemTypeMock.mockReset()
    restoreSourceItemTypeMock.mockReset()
  })

  it('refreshTable sends skip/limit and populates tableItems/total from the envelope', async () => {
    getSourceItemTypesMock.mockResolvedValue(page([makeSourceItemType()], 42))
    const store = useSourceItemTypesStore()

    await store.refreshTable({ skip: 25, limit: 25 })

    expect(getSourceItemTypesMock).toHaveBeenCalledWith(
      expect.objectContaining({ skip: 25, limit: 25 }),
    )
    expect(store.tableItems).toHaveLength(1)
    expect(store.total).toBe(42)
  })

  it('threads sortBy/sortDir into refreshTable as order_by/order_dir', async () => {
    getSourceItemTypesMock.mockResolvedValue(page([]))
    const store = useSourceItemTypesStore()
    store.setSort('name', 'desc')

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getSourceItemTypesMock).toHaveBeenCalledWith(
      expect.objectContaining({ order_by: 'name', order_dir: 'desc', skip: 0, limit: 25 }),
    )
  })

  it('keeps the picker-facing refresh() unpaginated and separate from tableItems', async () => {
    getSourceItemTypesMock.mockResolvedValue(page([makeSourceItemType({ id: 9 })], 1))
    const store = useSourceItemTypesStore()

    await store.refresh()

    expect(getSourceItemTypesMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ skip: expect.anything() }),
    )
    expect(store.items).toHaveLength(1)
    expect(store.tableItems).toHaveLength(0)
  })

  it('bumps refreshTrigger independently so the table can react to it', () => {
    const store = useSourceItemTypesStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })

  it('archive calls the archive api, replaces the item in place, and triggers a refresh', async () => {
    const archived = makeSourceItemType({ id: 1, archived: true })
    archiveSourceItemTypeMock.mockResolvedValue(archived)
    getSourceItemTypesMock.mockResolvedValue(page([makeSourceItemType({ id: 1, archived: false })]))
    const store = useSourceItemTypesStore()
    await store.refresh()
    const refreshesBefore = store.refreshTrigger

    await store.archive(1)

    expect(archiveSourceItemTypeMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(archived)
    expect(store.refreshTrigger).toBe(refreshesBefore + 1)
  })

  it('restore calls the restore api, replaces the item in place, and triggers a refresh', async () => {
    const restored = makeSourceItemType({ id: 1, archived: false })
    restoreSourceItemTypeMock.mockResolvedValue(restored)
    getSourceItemTypesMock.mockResolvedValue(page([makeSourceItemType({ id: 1, archived: true })]))
    const store = useSourceItemTypesStore()
    await store.refresh()
    const refreshesBefore = store.refreshTrigger

    await store.restore(1)

    expect(restoreSourceItemTypeMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(restored)
    expect(store.refreshTrigger).toBe(refreshesBefore + 1)
  })

  // Referencing an already-archived source item type is allowed. Pickers
  // built on `items` (via useArchivableOptions) need archived rows in the
  // list too, so the picker-facing refresh() always asks for them regardless
  // of the management table's own "Show archived" toggle.
  it('refresh always requests include_archived, independent of the showArchived toggle', async () => {
    getSourceItemTypesMock.mockResolvedValue(
      page([makeSourceItemType({ id: 1, archived: false }), makeSourceItemType({ id: 2, archived: true })]),
    )
    const store = useSourceItemTypesStore()

    await store.refresh()

    expect(getSourceItemTypesMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_archived: true }),
    )
    expect(store.items).toHaveLength(2)

    getSourceItemTypesMock.mockClear()
    store.toggleShowArchived()
    await store.refresh()

    expect(getSourceItemTypesMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_archived: true }),
    )
  })
})
