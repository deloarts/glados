import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { useServerTable } from '@/core/composables/useServerTable'
import { getCalculations } from '../api/getCalculations'
import { toolByKey } from '../registry'
import { calculationFilter, useCalculationsTableStores } from '../stores/calculationsTableStores'
import type { CalculationsContext } from '../stores/calculationsTableStores'
import type { CalculationListParams, CalculationSummaryResponse } from '../types/calculation'

/** The project or product a table is limited to; neither on the Calculations page. */
export interface CalculationsScope {
  projectId?: number
  productId?: number
  /** Also lists the calculations of the projects built on `productId`. */
  includeProductProjects?: boolean
}

export type CalculationRow = CalculationSummaryResponse & { _group?: string }

/**
 * Loads a calculations table a page at a time. Every filter of the row and
 * the sort are applied by the server, so each page is complete; grouping,
 * like in the catalogue, orders the rows of the current page. The tab of a
 * project or product has no filter row and no views bar, so it lists its
 * calculations unfiltered, ungrouped and most recently changed first.
 */
export function useCalculationsTable(context: CalculationsContext, scope: () => CalculationsScope) {
  const { t } = useI18n()
  const scoped = context !== 'page'
  const { view, filters: filtersStore } = useCalculationsTableStores(context)
  const { filters, clearTrigger, refreshTrigger } = storeToRefs(filtersStore)
  const { sortBy, sortDir, groupBy } = storeToRefs(view)

  const items = ref<CalculationSummaryResponse[]>([])
  const total = ref(0)

  function params(page: { first: number; rows: number }): CalculationListParams {
    const query: CalculationListParams = { skip: page.first, limit: page.rows }
    const { projectId, productId, includeProductProjects } = scope()
    if (projectId !== undefined) query.project_id = projectId
    if (productId !== undefined) {
      if (includeProductProjects) query.related_product_id = productId
      else query.product_id = productId
    }
    if (scoped) return query
    const title = calculationFilter(filters.value, 'title')
    if (typeof title === 'string' && title.trim()) query.search = title.trim()
    const tool = calculationFilter(filters.value, 'tool')
    if (typeof tool === 'string') query.tool = tool
    const owner = calculationFilter(filters.value, 'owner')
    if (owner === 'personal' || owner === 'project' || owner === 'product') query.owner = owner
    const status = calculationFilter(filters.value, 'status')
    if (status === 'draft' || status === 'released') query.released = status === 'released'
    if (calculationFilter(filters.value, 'author') === 'me') query.mine = true
    if (sortBy.value) {
      query.order_by = sortBy.value
      query.order_dir = sortDir.value
    }
    return query
  }

  // A late response for an earlier page or filter must not replace a newer one.
  const listFetch = useSequencedFetch(getCalculations)
  const { loading, failed } = listFetch

  async function fetch(query: CalculationListParams): Promise<void> {
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

  function toolLabel(row: CalculationSummaryResponse): string {
    const tool = toolByKey(row.tool)
    return tool ? t(tool.labelKey) : row.tool
  }

  function ownerLabel(row: CalculationSummaryResponse): string {
    if (row.project_number) return `${t('tools.calculations.owner.project')} ${row.project_number}`
    if (row.product_number) return `${t('tools.calculations.owner.product')} ${row.product_number}`
    return t('tools.calculations.owner.personal')
  }

  function statusLabel(row: CalculationSummaryResponse): string {
    return t(`tools.calculations.status.${row.released_at ? 'released' : 'draft'}`)
  }

  // Grouping keeps the server order within each group.
  const groupedItems = computed<CalculationRow[]>(() => {
    const group = groupBy.value
    if (scoped || !group) return items.value
    const label = group === 'tool' ? toolLabel : group === 'owner' ? ownerLabel : statusLabel
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
    toolLabel,
    ownerLabel,
  }
}
