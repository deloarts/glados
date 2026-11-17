import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { ProjectFilterParams } from '../../types/projectRequest'
import type { ProjectResponse } from '../../types/projectResponse'

const getProjectsMock =
  vi.fn<(params?: ProjectFilterParams) => Promise<PageResponse<ProjectResponse>>>()

vi.mock('../../api/getProjects', () => ({
  getProjects: (params?: ProjectFilterParams) => getProjectsMock(params),
}))
vi.mock('../../api/createProject', () => ({ createProject: vi.fn<() => void>() }))
vi.mock('../../api/updateProject', () => ({ updateProject: vi.fn<() => void>() }))
vi.mock('../../api/deleteProject', () => ({ deleteProject: vi.fn<() => void>() }))

import { deleteProject } from '../../api/deleteProject'
import { useProjectsStore } from '../projectsStore'

function makeProject(overrides: Partial<ProjectResponse> = {}): ProjectResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    project_number: 'PRJ-001',
    customer_id: null,
    customer: null,
    product_id: null,
    product: null,
    description: null,
    status: 'active',
    designated_user_id: 1,
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by: null,
    creator_id: 1,
    creator: null,
    production_time_budget: null,
    required_delivery_date_made: null,
    required_delivery_date_bought: null,
    edit_version: 0,
    actions: [],
    live_work: null,
    ...overrides,
  }
}

function page(items: ProjectResponse[], total = items.length): PageResponse<ProjectResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('projectsStore pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProjectsMock.mockReset()
  })

  it('refreshTable sends skip/limit and populates tableItems/total from the envelope', async () => {
    getProjectsMock.mockResolvedValue(page([makeProject()], 42))
    const store = useProjectsStore()

    await store.refreshTable({ skip: 25, limit: 25 })

    expect(getProjectsMock).toHaveBeenCalledWith(
      expect.objectContaining({ skip: 25, limit: 25 }),
    )
    expect(store.tableItems).toHaveLength(1)
    expect(store.total).toBe(42)
  })

  it('threads sortBy/sortDir into refreshTable as order_by/order_dir', async () => {
    getProjectsMock.mockResolvedValue(page([]))
    const store = useProjectsStore()
    store.setSort('project_number', 'desc')

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getProjectsMock).toHaveBeenCalledWith(
      expect.objectContaining({ order_by: 'project_number', order_dir: 'desc', skip: 0, limit: 25 }),
    )
  })

  it('keeps the picker-facing refresh() unpaginated and separate from tableItems', async () => {
    getProjectsMock.mockResolvedValue(page([makeProject({ id: 9 })], 1))
    const store = useProjectsStore()

    await store.refresh()

    expect(getProjectsMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ skip: expect.anything() }),
    )
    expect(store.items).toHaveLength(1)
    expect(store.tableItems).toHaveLength(0)
  })

  it('bumps refreshTrigger independently so the table can react to it', () => {
    const store = useProjectsStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })
})

describe('projectsStore column filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProjectsMock.mockReset()
    getProjectsMock.mockResolvedValue(page([]))
  })

  it('sends every column filter, counts it as active, and clearAll resets all of them', async () => {
    const store = useProjectsStore()
    const set = (field: string, value: unknown) => {
      store.filters[field] = { value, matchMode: 'equals' }
    }
    set('product_id', 2)
    set('description', 'gearbox')
    set('designated_user_id', 5)
    set('creator_id', 7)
    store.createdFrom = new Date(2026, 2, 10)
    store.createdTo = new Date(2026, 2, 12)
    store.deliveryMadeFrom = new Date(2026, 4, 1)
    store.deliveryMadeTo = new Date(2026, 4, 3)
    store.deliveryBoughtFrom = new Date(2026, 5, 1)
    store.deliveryBoughtTo = new Date(2026, 5, 3)

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getProjectsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        product_id: 2,
        description: 'gearbox',
        designated_user_id: 5,
        creator_id: 7,
        created_from: '2026-03-10',
        created_to: '2026-03-12',
        required_delivery_date_made_from: '2026-05-01',
        required_delivery_date_made_to: '2026-05-03',
        required_delivery_date_bought_from: '2026-06-01',
        required_delivery_date_bought_to: '2026-06-03',
      }),
    )
    expect(store.hasActiveFilters).toBe(true)

    store.clearAll()
    expect(store.hasActiveFilters).toBe(false)
    expect(store.deliveryBoughtTo).toBeNull()

    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getProjectsMock).toHaveBeenLastCalledWith({ skip: 0, limit: 25 })
  })

  it('counts a date bound alone as an active filter', () => {
    const store = useProjectsStore()
    store.deliveryMadeTo = new Date(2026, 4, 3)
    expect(store.hasActiveFilters).toBe(true)
  })
})

describe('projectsStore remove', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProjectsMock.mockReset()
    vi.mocked(deleteProject).mockReset()
  })

  it('sends the edit version the caller showed', async () => {
    await useProjectsStore().remove(7, 4)

    expect(deleteProject).toHaveBeenCalledWith(7, 4)
  })

  it('sends the edit version of the row it holds when the caller names none', async () => {
    getProjectsMock.mockResolvedValue(page([makeProject({ id: 7, edit_version: 2 })]))
    const store = useProjectsStore()
    await store.refreshTable({ skip: 0, limit: 25 })

    await store.remove(7)

    expect(deleteProject).toHaveBeenCalledWith(7, 2)
  })
})
