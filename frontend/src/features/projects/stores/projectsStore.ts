import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { FilterMatchMode } from '@openvue/core/api'
import type { DataTableFilterMeta } from 'openvue/datatable'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { dateToParam } from '@/core/utils/dates'
import { filterMetaValue, hasActiveFilterMeta } from '@/core/utils/filterMeta'
import { createProject } from '../api/createProject'
import { deleteProject } from '../api/deleteProject'
import { getProjects } from '../api/getProjects'
import { updateProject } from '../api/updateProject'

import type {
  ProjectCreateRequest,
  ProjectFilterParams,
  ProjectSortBy,
  ProjectSortDir,
  ProjectUpdateRequest,
} from '../types/projectRequest'
import type { ProjectResponse } from '../types/projectResponse'

export type ProjectGroupBy = 'customer' | 'status' | null

function createEmptyFilters(): DataTableFilterMeta {
  return {
    project_number: { value: null, matchMode: FilterMatchMode.CONTAINS },
    customer_id: { value: null, matchMode: FilterMatchMode.EQUALS },
    status: { value: null, matchMode: FilterMatchMode.EQUALS },
    product_id: { value: null, matchMode: FilterMatchMode.EQUALS },
    description: { value: null, matchMode: FilterMatchMode.CONTAINS },
    designated_user_id: { value: null, matchMode: FilterMatchMode.EQUALS },
    creator_id: { value: null, matchMode: FilterMatchMode.EQUALS },
  }
}

export const useProjectsStore = defineStore('projects', () => {
  // Two sequenced fetchers, since the picker list and the table page are
  // unrelated and must not discard each other's fetches.
  const pickerFetch = useSequencedFetch(getProjects)
  const tableFetch = useSequencedFetch(getProjects)
  const loading = computed(() => pickerFetch.loading.value || tableFetch.loading.value)
  const error = computed(() => pickerFetch.error.value ?? tableFetch.error.value)
  const items = ref<ProjectResponse[]>([])
  // The management table's current page. Kept separate from `items` above,
  // which other features may read as the *complete* project list. Paging
  // the table must not shrink what those pickers see.
  const tableItems = ref<ProjectResponse[]>([])
  const total = ref(0)
  const filters = ref<DataTableFilterMeta>(createEmptyFilters())
  const clearTrigger = ref(0)
  const refreshTrigger = ref(0)
  const search = ref('')
  const showActions = ref(false)
  const sortBy = ref<ProjectSortBy | null>(null)
  const sortDir = ref<ProjectSortDir>('asc')
  const groupBy = ref<ProjectGroupBy>(null)
  // Date ranges live outside the OpenVue filter meta because a range is two
  // bounds, see useDateRangeFilter for how the table binds them.
  const createdFrom = ref<Date | null>(null)
  const createdTo = ref<Date | null>(null)
  const deliveryMadeFrom = ref<Date | null>(null)
  const deliveryMadeTo = ref<Date | null>(null)
  const deliveryBoughtFrom = ref<Date | null>(null)
  const deliveryBoughtTo = ref<Date | null>(null)
  const dateRefs = [
    createdFrom,
    createdTo,
    deliveryMadeFrom,
    deliveryMadeTo,
    deliveryBoughtFrom,
    deliveryBoughtTo,
  ]

  const hasActiveFilters = computed<boolean>(() => {
    if (search.value !== '') return true
    if (dateRefs.some((r) => r.value !== null)) return true
    return hasActiveFilterMeta(filters.value)
  })

  function buildParams(page?: { skip: number; limit: number }): ProjectFilterParams {
    const getValue = (field: string): unknown => filterMetaValue(filters.value, field)

    const params: ProjectFilterParams = {}

    if (search.value) params.search = search.value

    const projectNumber = getValue('project_number')
    if (projectNumber) params.project_number = projectNumber as string

    const customerId = getValue('customer_id')
    if (customerId) params.customer_id = customerId as number

    const status = getValue('status')
    if (status !== null && status !== undefined)
      params.status = status as ProjectFilterParams['status']

    const productId = getValue('product_id')
    if (productId) params.product_id = productId as number

    const description = getValue('description')
    if (description) params.description = description as string

    const designatedUserId = getValue('designated_user_id')
    if (designatedUserId) params.designated_user_id = designatedUserId as number

    const creatorId = getValue('creator_id')
    if (creatorId) params.creator_id = creatorId as number

    const toParam = (d: Date | null): string | undefined => dateToParam(d) ?? undefined
    if (createdFrom.value) params.created_from = toParam(createdFrom.value)
    if (createdTo.value) params.created_to = toParam(createdTo.value)
    if (deliveryMadeFrom.value)
      params.required_delivery_date_made_from = toParam(deliveryMadeFrom.value)
    if (deliveryMadeTo.value) params.required_delivery_date_made_to = toParam(deliveryMadeTo.value)
    if (deliveryBoughtFrom.value)
      params.required_delivery_date_bought_from = toParam(deliveryBoughtFrom.value)
    if (deliveryBoughtTo.value)
      params.required_delivery_date_bought_to = toParam(deliveryBoughtTo.value)

    if (sortBy.value) {
      params.order_by = sortBy.value
      params.order_dir = sortDir.value
    }

    if (page) {
      params.skip = page.skip
      params.limit = page.limit
    }

    return params
  }

  // Feeds items, the full list other features pick from.
  async function refresh(params?: ProjectFilterParams): Promise<void> {
    // The picker list is independent of the management table: its search,
    // column filters and sort must never narrow what other screens pick from.
    const response = await pickerFetch.run(params ?? {})
    if (!response) return

    items.value = response.items
  }

  // The management table's fetch is paginated, feeding `tableItems`/`total`.
  async function refreshTable(page?: { skip: number; limit: number }): Promise<void> {
    const response = await tableFetch.run(buildParams(page))
    if (!response) return

    tableItems.value = response.items
    total.value = response.total
  }

  function triggerRefresh(): void {
    refreshTrigger.value++
  }

  function toggleShowActions(): void {
    showActions.value = !showActions.value
  }

  function setSort(field: ProjectSortBy, dir: ProjectSortDir): void {
    sortBy.value = field
    sortDir.value = dir
  }

  function clearSort(): void {
    sortBy.value = null
    sortDir.value = 'asc'
  }

  function setGroupBy(value: Exclude<ProjectGroupBy, null>): void {
    groupBy.value = groupBy.value === value ? null : value
  }

  function clearGroupBy(): void {
    groupBy.value = null
  }

  function clearAll(): void {
    filters.value = createEmptyFilters()
    search.value = ''
    for (const r of dateRefs) r.value = null
    clearTrigger.value++
  }

  function clear(): void {
    items.value = []
    tableItems.value = []
    total.value = 0
  }

  async function create(payload: ProjectCreateRequest): Promise<ProjectResponse> {
    const created = await createProject(payload)
    items.value.push(created)
    triggerRefresh()
    return created
  }

  async function update(
    projectId: number,
    payload: ProjectUpdateRequest,
  ): Promise<ProjectResponse> {
    const updated = await updateProject(projectId, payload)
    const index = items.value.findIndex((p) => p.id === projectId)
    if (index !== -1) {
      items.value[index] = updated
    }
    triggerRefresh()
    return updated
  }

  // The edit version of the project as the caller showed it, or as this
  // store holds it, so a project changed meanwhile is refused.
  async function remove(projectId: number, editVersion?: number): Promise<void> {
    const held = [...items.value, ...tableItems.value].find((p) => p.id === projectId)
    const version = editVersion ?? held?.edit_version
    if (version === undefined) throw new Error(`Project #${projectId} is not loaded.`)
    await deleteProject(projectId, version)
    items.value = items.value.filter((p) => p.id !== projectId)
    triggerRefresh()
  }

  return {
    loading,
    error,
    items,
    tableItems,
    total,
    filters,
    clearTrigger,
    refreshTrigger,
    search,
    showActions,
    sortBy,
    sortDir,
    groupBy,
    createdFrom,
    createdTo,
    deliveryMadeFrom,
    deliveryMadeTo,
    deliveryBoughtFrom,
    deliveryBoughtTo,

    hasActiveFilters,

    refresh,
    refreshTable,
    triggerRefresh,
    toggleShowActions,
    setSort,
    clearSort,
    setGroupBy,
    clearGroupBy,
    clearAll,
    clear,
    create,
    update,
    remove,
  }
})
