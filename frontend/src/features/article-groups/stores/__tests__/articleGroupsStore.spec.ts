import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { ArticleGroupFilterParams } from '../../types/articleGroupRequest'
import type { ArticleGroupResponse } from '../../types/articleGroupResponse'

const getArticleGroupsMock =
  vi.fn<(params?: ArticleGroupFilterParams) => Promise<PageResponse<ArticleGroupResponse>>>()

vi.mock('../../api/getArticleGroups', () => ({
  getArticleGroups: (params?: ArticleGroupFilterParams) => getArticleGroupsMock(params),
}))
vi.mock('../../api/createArticleGroup', () => ({ createArticleGroup: vi.fn<() => void>() }))
vi.mock('../../api/updateArticleGroup', () => ({ updateArticleGroup: vi.fn<() => void>() }))

const archiveArticleGroupMock =
  vi.fn<(groupId: number) => Promise<ArticleGroupResponse>>()
const restoreArticleGroupMock =
  vi.fn<(groupId: number) => Promise<ArticleGroupResponse>>()

vi.mock('../../api/archiveArticleGroup', () => ({
  archiveArticleGroup: (groupId: number) => archiveArticleGroupMock(groupId),
}))
vi.mock('../../api/restoreArticleGroup', () => ({
  restoreArticleGroup: (groupId: number) => restoreArticleGroupMock(groupId),
}))

import { useArticleGroupsStore } from '../articleGroupsStore'

function makeArticleGroup(overrides: Partial<ArticleGroupResponse> = {}): ArticleGroupResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: { enGB: 'Sheet Metal' },
    label_color: '#ffffff',
    label_font_color: '#000000',
    description: { enGB: 'Sheet metal parts' },
    creator_id: 1,
    creator: null,
    ...overrides,
  }
}

function page(
  items: ArticleGroupResponse[],
  total = items.length,
): PageResponse<ArticleGroupResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('articleGroupsStore pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getArticleGroupsMock.mockReset()
    archiveArticleGroupMock.mockReset()
    restoreArticleGroupMock.mockReset()
  })

  it('refreshTable sends skip/limit and populates tableItems/total from the envelope', async () => {
    getArticleGroupsMock.mockResolvedValue(page([makeArticleGroup()], 42))
    const store = useArticleGroupsStore()

    await store.refreshTable({ skip: 25, limit: 25 })

    expect(getArticleGroupsMock).toHaveBeenCalledWith(
      expect.objectContaining({ skip: 25, limit: 25 }),
    )
    expect(store.tableItems).toHaveLength(1)
    expect(store.total).toBe(42)
  })

  it('threads sortBy/sortDir into refreshTable as order_by/order_dir', async () => {
    getArticleGroupsMock.mockResolvedValue(page([]))
    const store = useArticleGroupsStore()
    store.setSort('name', 'desc')

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getArticleGroupsMock).toHaveBeenCalledWith(
      expect.objectContaining({ order_by: 'name', order_dir: 'desc', skip: 0, limit: 25 }),
    )
  })

  it('keeps the picker-facing refresh() unpaginated and separate from tableItems', async () => {
    getArticleGroupsMock.mockResolvedValue(page([makeArticleGroup({ id: 9 })], 1))
    const store = useArticleGroupsStore()

    await store.refresh()

    expect(getArticleGroupsMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ skip: expect.anything() }),
    )
    expect(store.items).toHaveLength(1)
    expect(store.tableItems).toHaveLength(0)
  })

  it('bumps refreshTrigger independently so the table can react to it', () => {
    const store = useArticleGroupsStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })

  it('showArchived starts false, toggles independently, feeds include_archived in buildParams, counts in hasActiveFilters, and resets on clearAll', async () => {
    getArticleGroupsMock.mockResolvedValue(page([]))
    const store = useArticleGroupsStore()

    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getArticleGroupsMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ include_archived: expect.anything() }),
    )

    store.toggleShowArchived()
    expect(store.showArchived).toBe(true)
    expect(store.hasActiveFilters).toBe(true)

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getArticleGroupsMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_archived: true }),
    )

    store.clearAll()
    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  // Referencing an already-archived article group is allowed: pickers built
  // on `items` (via useArchivableOptions) need archived rows in the list
  // too, so the picker-facing refresh() always asks for them regardless of
  // the management table's own "Show archived" toggle.
  it('refresh always requests include_archived, independent of the showArchived toggle', async () => {
    getArticleGroupsMock.mockResolvedValue(
      page([makeArticleGroup({ id: 1, archived: false }), makeArticleGroup({ id: 2, archived: true })]),
    )
    const store = useArticleGroupsStore()

    await store.refresh()

    expect(getArticleGroupsMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_archived: true }),
    )
    expect(store.items).toHaveLength(2)

    getArticleGroupsMock.mockClear()
    store.toggleShowArchived()
    await store.refresh()

    expect(getArticleGroupsMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_archived: true }),
    )
  })

  it('archive calls the archive api, replaces the item in place, and triggers a refresh', async () => {
    const archived = makeArticleGroup({ id: 1, archived: true })
    archiveArticleGroupMock.mockResolvedValue(archived)
    getArticleGroupsMock.mockResolvedValue(page([makeArticleGroup({ id: 1, archived: false })]))
    const store = useArticleGroupsStore()
    await store.refresh()
    const refreshesBefore = store.refreshTrigger

    await store.archive(1)

    expect(archiveArticleGroupMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(archived)
    expect(store.refreshTrigger).toBe(refreshesBefore + 1)
  })

  it('restore calls the restore api, replaces the item in place, and triggers a refresh', async () => {
    const restored = makeArticleGroup({ id: 1, archived: false })
    restoreArticleGroupMock.mockResolvedValue(restored)
    getArticleGroupsMock.mockResolvedValue(page([makeArticleGroup({ id: 1, archived: true })]))
    const store = useArticleGroupsStore()
    await store.refresh()
    const refreshesBefore = store.refreshTrigger

    await store.restore(1)

    expect(restoreArticleGroupMock).toHaveBeenCalledWith(1)
    expect(store.items[0]).toEqual(restored)
    expect(store.refreshTrigger).toBe(refreshesBefore + 1)
  })
})
