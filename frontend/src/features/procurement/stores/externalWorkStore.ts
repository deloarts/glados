import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { TABLE_DEFAULT_ROWS } from '@/core/constants/table'
import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { dateToParam } from '@/core/utils/dates'
import { getExternalWork } from '../api/getExternalWork'

import type {
  ExternalWorkAlert,
  ExternalWorkGroupBy,
  ExternalWorkQuery,
  ExternalWorkRow,
  ExternalWorkStage,
} from '../types/externalWork'

/**
 * The procurement list of external work: its filters, the page shown and
 * the rows of that page. Sorting is fixed server side to the latest pickup,
 * so the only view choice is how the page is grouped.
 */
export const useExternalWorkStore = defineStore('externalWork', () => {
  const search = ref('')
  const groupBy = ref<ExternalWorkGroupBy | null>('method')
  const onlyWithSupplier = ref(false)
  const onlyCritical = ref(false)

  // The column filters of the table row.
  const stages = ref<ExternalWorkStage[]>([])
  const part = ref('')
  const lotIds = ref<number[]>([])
  const projectIds = ref<number[]>([])
  const productIds = ref<number[]>([])
  const methodId = ref<number | null>(null)
  const readyFrom = ref<Date | null>(null)
  const readyTo = ref<Date | null>(null)
  const latestFrom = ref<Date | null>(null)
  const latestTo = ref<Date | null>(null)
  const backByFrom = ref<Date | null>(null)
  const backByTo = ref<Date | null>(null)
  const supplierId = ref<number | null>(null)
  const alerts = ref<ExternalWorkAlert[]>([])

  const first = ref(0)
  const rows = ref(TABLE_DEFAULT_ROWS)
  const items = ref<ExternalWorkRow[]>([])
  const total = ref(0)

  const hasActiveFilters = computed(
    () =>
      search.value.trim() !== '' ||
      onlyWithSupplier.value ||
      onlyCritical.value ||
      stages.value.length > 0 ||
      part.value.trim() !== '' ||
      lotIds.value.length > 0 ||
      projectIds.value.length > 0 ||
      productIds.value.length > 0 ||
      methodId.value !== null ||
      readyFrom.value !== null ||
      latestFrom.value !== null ||
      backByFrom.value !== null ||
      supplierId.value !== null ||
      alerts.value.length > 0,
  )

  function query(): ExternalWorkQuery {
    const term = search.value.trim()
    const partTerm = part.value.trim()
    return {
      skip: first.value,
      limit: rows.value,
      ...(term ? { search: term } : {}),
      ...(onlyWithSupplier.value ? { only_with_supplier: true } : {}),
      ...(onlyCritical.value ? { only_critical: true } : {}),
      ...(stages.value.length > 0 ? { stages: stages.value } : {}),
      ...(partTerm ? { part: partTerm } : {}),
      ...(lotIds.value.length > 0 ? { lot_ids: lotIds.value } : {}),
      ...(projectIds.value.length > 0 ? { project_ids: projectIds.value } : {}),
      ...(productIds.value.length > 0 ? { product_ids: productIds.value } : {}),
      ...(methodId.value !== null ? { fabrication_method_id: methodId.value } : {}),
      ...(readyFrom.value ? { ready_from: dateToParam(readyFrom.value) } : {}),
      ...(readyTo.value ? { ready_to: dateToParam(readyTo.value) } : {}),
      ...(latestFrom.value ? { latest_pickup_from: dateToParam(latestFrom.value) } : {}),
      ...(latestTo.value ? { latest_pickup_to: dateToParam(latestTo.value) } : {}),
      ...(backByFrom.value ? { back_by_from: dateToParam(backByFrom.value) } : {}),
      ...(backByTo.value ? { back_by_to: dateToParam(backByTo.value) } : {}),
      ...(supplierId.value !== null ? { supplier_id: supplierId.value } : {}),
      ...(alerts.value.length > 0 ? { alerts: alerts.value } : {}),
    }
  }

  const { run, loading, error } = useSequencedFetch(getExternalWork)

  async function fetch(): Promise<void> {
    const page = await run(query())
    if (!page) return
    items.value = page.items
    total.value = page.total
  }

  /** A changed filter starts again on the first page. */
  async function refilter(): Promise<void> {
    first.value = 0
    await fetch()
  }

  async function setPage(nextFirst: number, nextRows: number): Promise<void> {
    first.value = nextFirst
    rows.value = nextRows
    await fetch()
  }

  async function toggleOnlyWithSupplier(): Promise<void> {
    onlyWithSupplier.value = !onlyWithSupplier.value
    await refilter()
  }

  async function toggleOnlyCritical(): Promise<void> {
    onlyCritical.value = !onlyCritical.value
    await refilter()
  }

  async function clearAll(): Promise<void> {
    search.value = ''
    onlyWithSupplier.value = false
    onlyCritical.value = false
    groupBy.value = 'method'
    stages.value = []
    part.value = ''
    lotIds.value = []
    projectIds.value = []
    productIds.value = []
    methodId.value = null
    readyFrom.value = null
    readyTo.value = null
    latestFrom.value = null
    latestTo.value = null
    backByFrom.value = null
    backByTo.value = null
    supplierId.value = null
    alerts.value = []
    await refilter()
  }

  return {
    search,
    groupBy,
    onlyWithSupplier,
    onlyCritical,
    stages,
    part,
    lotIds,
    projectIds,
    productIds,
    methodId,
    readyFrom,
    readyTo,
    latestFrom,
    latestTo,
    backByFrom,
    backByTo,
    supplierId,
    alerts,
    first,
    rows,
    items,
    total,
    loading,
    error,
    hasActiveFilters,
    query,
    fetch,
    refilter,
    setPage,
    toggleOnlyWithSupplier,
    toggleOnlyCritical,
    clearAll,
  }
})
