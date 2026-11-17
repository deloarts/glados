// Filters, loading state and results for the KPI page. load() fetches every
// result endpoint together, plus the previous period's summary for the
// tile deltas.
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { toDateKey } from '@/core/utils/dates'
import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { getProductionKpiSummary } from '../api/getProductionKpiSummary'
import { getProductionKpiWeekly } from '../api/getProductionKpiWeekly'
import { getProductionKpiUtilization } from '../api/getProductionKpiUtilization'
import { getProductionKpiEstimateAccuracy } from '../api/getProductionKpiEstimateAccuracy'
import { getProductionKpiWaitingTime } from '../api/getProductionKpiWaitingTime'
import { getProductionKpiLateLots } from '../api/getProductionKpiLateLots'
import { getProductionKpiQualityByItem } from '../api/getProductionKpiQualityByItem'
import { getProductionKpiRejectedPerSupplier } from '../api/getProductionKpiRejectedPerSupplier'
import { getProductionKpiScrapByReason } from '../api/getProductionKpiScrapByReason'
import { previousPeriodOf, resolvePeriodPreset } from '../utils/periodPresets'

import type { ProductionKpiPeriodPreset } from '../utils/periodPresets'
import type { ProductionKpiFilterParams } from '../types/productionKpiFilterParams'
import type {
  ProductionKpiEstimateAccuracyResult,
  ProductionKpiLateLotsResult,
  ProductionKpiQualityByItemResult,
  ProductionKpiRejectedPerSupplierResult,
  ProductionKpiScrapByReasonResult,
  ProductionKpiSummaryResult,
  ProductionKpiUtilizationResult,
  ProductionKpiWaitingTimeResult,
  ProductionKpiWeeklyResult,
} from '../types/productionKpiResponse'
import type { ProjectRef } from '@/core/types/projectRef'
import type { CustomerResponse } from '@/features/customers'

const DEFAULT_PRESET: ProductionKpiPeriodPreset = 'this_month'

interface LoadResult {
  summary: ProductionKpiSummaryResult
  previousSummary: ProductionKpiSummaryResult
  weekly: ProductionKpiWeeklyResult
  utilization: ProductionKpiUtilizationResult
  estimateAccuracy: ProductionKpiEstimateAccuracyResult
  waitingTime: ProductionKpiWaitingTimeResult
  lateLots: ProductionKpiLateLotsResult
  qualityByItem: ProductionKpiQualityByItemResult
}

export const useProductionKpiStore = defineStore('productionKpi', () => {
  // ── Filters ─────────────────────────────────────────────────────────

  const periodPreset = ref<ProductionKpiPeriodPreset>(DEFAULT_PRESET)
  // Only read when periodPreset === 'custom'.
  const customRange = ref<[Date, Date] | null>(null)
  // 'machine:<id>' | 'pool:<id>' | null; see KpiMachineOrPoolSelect.vue.
  const machineOrPoolKey = ref<string | null>(null)
  const selectedProject = ref<ProjectRef | null>(null)
  const selectedCustomer = ref<CustomerResponse | null>(null)

  const machineId = computed<number | null>(() => {
    const key = machineOrPoolKey.value
    return key?.startsWith('machine:') ? Number(key.slice('machine:'.length)) : null
  })

  const machinePoolId = computed<number | null>(() => {
    const key = machineOrPoolKey.value
    return key?.startsWith('pool:') ? Number(key.slice('pool:'.length)) : null
  })

  const dateRange = computed<[Date, Date]>(() => {
    if (periodPreset.value === 'custom') {
      return customRange.value ?? resolvePeriodPreset(DEFAULT_PRESET)
    }
    return resolvePeriodPreset(periodPreset.value)
  })

  const queryParams = computed<ProductionKpiFilterParams>(() => {
    const [from, to] = dateRange.value
    return {
      date_from: toDateKey(from),
      date_to: toDateKey(to),
      machine_id: machineId.value,
      machine_pool_id: machinePoolId.value,
      project_id: selectedProject.value?.id ?? null,
      customer_id: selectedCustomer.value?.id ?? null,
    }
  })

  const previousQueryParams = computed<ProductionKpiFilterParams>(() => {
    const [from, to] = dateRange.value
    const [prevFrom, prevTo] = previousPeriodOf(from, to)
    return {
      ...queryParams.value,
      date_from: toDateKey(prevFrom),
      date_to: toDateKey(prevTo),
    }
  })

  const hasActiveFilters = computed(
    () =>
      periodPreset.value !== DEFAULT_PRESET ||
      machineOrPoolKey.value !== null ||
      selectedProject.value !== null ||
      selectedCustomer.value !== null,
  )

  function clearFilters(): void {
    periodPreset.value = DEFAULT_PRESET
    customRange.value = null
    machineOrPoolKey.value = null
    selectedProject.value = null
    selectedCustomer.value = null
  }

  // ── Results ─────────────────────────────────────────────────────────

  const summary = ref<ProductionKpiSummaryResult | null>(null)
  const previousSummary = ref<ProductionKpiSummaryResult | null>(null)
  const weekly = ref<ProductionKpiWeeklyResult | null>(null)
  const utilization = ref<ProductionKpiUtilizationResult | null>(null)
  const estimateAccuracy = ref<ProductionKpiEstimateAccuracyResult | null>(null)
  const waitingTime = ref<ProductionKpiWaitingTimeResult | null>(null)
  const lateLots = ref<ProductionKpiLateLotsResult | null>(null)
  const qualityByItem = ref<ProductionKpiQualityByItemResult | null>(null)
  const scrapByReason = ref<ProductionKpiScrapByReasonResult | null>(null)
  const rejectedPerSupplier = ref<ProductionKpiRejectedPerSupplierResult | null>(null)

  const { loading, error, run } = useSequencedFetch(
    async (filter: ProductionKpiFilterParams, previousFilter: ProductionKpiFilterParams) => {
      const [
        summaryResult,
        previousSummaryResult,
        weeklyResult,
        utilizationResult,
        estimateAccuracyResult,
        waitingTimeResult,
        lateLotsResult,
        qualityByItemResult,
      ] = await Promise.all([
        getProductionKpiSummary(filter),
        getProductionKpiSummary(previousFilter),
        getProductionKpiWeekly(filter),
        getProductionKpiUtilization(filter),
        getProductionKpiEstimateAccuracy(filter),
        getProductionKpiWaitingTime(filter),
        getProductionKpiLateLots(filter),
        getProductionKpiQualityByItem(filter),
      ])
      const result: LoadResult = {
        summary: summaryResult,
        previousSummary: previousSummaryResult,
        weekly: weeklyResult,
        utilization: utilizationResult,
        estimateAccuracy: estimateAccuracyResult,
        waitingTime: waitingTimeResult,
        lateLots: lateLotsResult,
        qualityByItem: qualityByItemResult,
      }
      return result
    },
  )

  async function load(): Promise<void> {
    const result = await run(queryParams.value, previousQueryParams.value)
    if (!result) return
    summary.value = result.summary
    previousSummary.value = result.previousSummary
    weekly.value = result.weekly
    utilization.value = result.utilization
    estimateAccuracy.value = result.estimateAccuracy
    waitingTime.value = result.waitingTime
    lateLots.value = result.lateLots
    qualityByItem.value = result.qualityByItem
  }

  // Scrap by reason and rejected per supplier have their own fetch, so their
  // failure never blocks the rest of the page.
  interface ScrapLoadResult {
    scrapByReason: ProductionKpiScrapByReasonResult
    rejectedPerSupplier: ProductionKpiRejectedPerSupplierResult
  }

  const {
    loading: scrapLoading,
    error: scrapError,
    run: runScrapKpis,
  } = useSequencedFetch(async (filter: ProductionKpiFilterParams): Promise<ScrapLoadResult> => {
    const [scrapByReasonResult, rejectedPerSupplierResult] = await Promise.all([
      getProductionKpiScrapByReason(filter),
      getProductionKpiRejectedPerSupplier(filter),
    ])
    return { scrapByReason: scrapByReasonResult, rejectedPerSupplier: rejectedPerSupplierResult }
  })

  async function loadScrapKpis(): Promise<void> {
    const result = await runScrapKpis(queryParams.value)
    if (!result) return
    scrapByReason.value = result.scrapByReason
    rejectedPerSupplier.value = result.rejectedPerSupplier
  }

  return {
    periodPreset,
    customRange,
    machineOrPoolKey,
    selectedProject,
    selectedCustomer,
    dateRange,
    queryParams,
    previousQueryParams,
    hasActiveFilters,
    clearFilters,
    summary,
    previousSummary,
    weekly,
    utilization,
    estimateAccuracy,
    waitingTime,
    lateLots,
    qualityByItem,
    scrapByReason,
    rejectedPerSupplier,
    loading,
    error,
    scrapLoading,
    scrapError,
    load,
    loadScrapKpis,
  }
})
