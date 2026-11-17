import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { useServerTable } from '@/core/composables/useServerTable'
import { getChecklists } from '../api/getChecklists'
import { checklistFilter, useChecklistsTableStores } from '../stores/checklistsTableStores'
import type { ChecklistsContext } from '../stores/checklistsTableStores'
import type { ChecklistListParams, ChecklistSummaryResponse } from '../types/checklist'
import { typeLabel } from '../utils/definitions'
import { checklistStatus, ownerOf } from '../utils/owner'

/** The project or product a table is limited to; neither on the Checklists page. */
export interface ChecklistsScope {
  projectId?: number
  productId?: number
  /** Also lists the checklists of the projects built on `productId`. */
  includeProductProjects?: boolean
}

export type ChecklistRow = ChecklistSummaryResponse & { _group?: string }

/**
 * Loads a checklists table a page at a time, the latest revision of each
 * checklist. Every filter of the row and the sort are applied by the
 * server, so each page is complete. Whether an unreleased checklist is a
 * draft or done follows from its answers, which the server cannot filter
 * by, so the status filter tells released from not released. Grouping,
 * like in the catalogue, orders the rows of the current page. The tab of a
 * project or product has no filter row and no views bar, so it lists its
 * checklists unfiltered, ungrouped and most recently changed first.
 */
export function useChecklistsTable(context: ChecklistsContext, scope: () => ChecklistsScope) {
  const { t } = useI18n()
  const scoped = context !== 'page'
  const { view, filters: filtersStore } = useChecklistsTableStores(context)
  const { filters, clearTrigger, refreshTrigger } = storeToRefs(filtersStore)
  const { sortBy, sortDir, groupBy } = storeToRefs(view)

  const items = ref<ChecklistSummaryResponse[]>([])
  const total = ref(0)

  function params(page: { first: number; rows: number }): ChecklistListParams {
    const query: ChecklistListParams = { skip: page.first, limit: page.rows }
    const { projectId, productId, includeProductProjects } = scope()
    if (projectId !== undefined) query.project_id = projectId
    if (productId !== undefined) {
      if (includeProductProjects) query.related_product_id = productId
      else query.product_id = productId
    }
    if (scoped) return query
    const title = checklistFilter(filters.value, 'title')
    if (typeof title === 'string' && title.trim()) query.search = title.trim()
    const type = checklistFilter(filters.value, 'type')
    if (typeof type === 'string') query.type = type
    const owner = checklistFilter(filters.value, 'owner')
    if (owner === 'personal' || owner === 'project' || owner === 'product') query.owner = owner
    const verdict = checklistFilter(filters.value, 'verdict')
    if (verdict === 'open' || verdict === 'passed' || verdict === 'failed') query.verdict = verdict
    const status = checklistFilter(filters.value, 'status')
    if (status === 'released' || status === 'unreleased') query.released = status === 'released'
    if (checklistFilter(filters.value, 'author') === 'me') query.mine = true
    if (sortBy.value) {
      query.order_by = sortBy.value
      query.order_dir = sortDir.value
    }
    return query
  }

  // A late response for an earlier page or filter must not replace a newer one.
  const listFetch = useSequencedFetch(getChecklists)
  const { loading, failed } = listFetch

  async function fetch(query: ChecklistListParams): Promise<void> {
    const page = await listFetch.run(query)
    if (!page) return
    items.value = page.items
    total.value = page.total
  }

  const { first, rows, fetchItems, resetAndFetch, onPage, onFilter } = useServerTable({
    fetchParams: params,
    fetch,
  })

  watch(clearTrigger, resetAndFetch)
  watch(refreshTrigger, fetchItems)
  watch([sortBy, sortDir], resetAndFetch)
  watch(() => [scope().projectId, scope().productId, scope().includeProductProjects], resetAndFetch)

  const translate = (key: string, values?: Record<string, unknown>) => (values ? t(key, values) : t(key))

  function typeName(row: ChecklistSummaryResponse): string {
    return typeLabel(row.type, translate)
  }

  function ownerLabel(row: ChecklistSummaryResponse): string {
    const o = ownerOf(row)
    return o.kind === 'personal' ? t('checklists.owner.personal') : `${t(`checklists.owner.${o.kind}`)} ${o.label}`
  }

  const GROUP_LABELS: Record<NonNullable<typeof groupBy.value>, (row: ChecklistSummaryResponse) => string> = {
    type: typeName,
    owner: ownerLabel,
    verdict: (row) => t(`checklists.verdicts.${row.verdict}`),
    status: (row) => t(`checklists.status.${checklistStatus(row)}`),
  }

  // Grouping keeps the server order within each group.
  const groupedItems = computed<ChecklistRow[]>(() => {
    const group = groupBy.value
    if (scoped || !group) return items.value
    const label = GROUP_LABELS[group]
    return items.value
      .map((row, index) => ({ row: { ...row, _group: label(row) }, index }))
      .sort((a, b) => a.row._group.localeCompare(b.row._group) || a.index - b.index)
      .map(({ row }) => row)
  })

  return {
    view,
    filtersStore,
    filters,
    items: groupedItems,
    total,
    loading,
    failed,
    first,
    rows,
    onPage,
    onFilter,
    reload: fetchItems,
    typeName,
    ownerLabel,
  }
}
