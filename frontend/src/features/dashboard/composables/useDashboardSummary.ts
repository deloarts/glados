import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'

import { useProductionQueueStore } from '@/features/production'
import { useNotificationsStore } from '@/features/notifications'
import { useProductionSchedule } from '@/features/production'
import { computeProductionSchedule } from '@/features/production'
import { getProductionWip } from '@/features/production'
import { getMadeItems } from '@/features/made-items'
import { getBoughtItems } from '@/features/bought-items'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { toLocalDayStart, todayStart } from '@/core/utils/dates'
import { getDashboardSummary } from '../api/getDashboardSummary'

import type { ProductionOrderResponse } from '@/features/production'
import type { WipLotResponse } from '@/features/production'
import type { DashboardSummaryResponse } from '../types/dashboardSummaryResponse'

const MIDNIGHT_CHECK_INTERVAL_MS = 5 * 60 * 1000
// Recent made and bought items kept after merging the two lists.
const RECENT_ITEMS_LIMIT = 6

export interface RecentCatalogueItem {
  type: 'made' | 'bought'
  itemId: number
  label: string
  partNumber: string | null
  // Made items only; a bought item's revision is not part of its label.
  revision: string | null
  created: string
}

// How many rows of one list hold each status, from the summary's counts.
export type StatusCounts = Partial<Record<string, number>>

function toStatusCounts(entries: { status: string; count: number }[]): StatusCounts {
  return Object.fromEntries(entries.map((entry) => [entry.status, entry.count]))
}

function sumCounts(counts: StatusCounts): number {
  return Object.values(counts).reduce<number>((sum, count) => sum + (count ?? 0), 0)
}

// Every dashboard data source, each fetched on its own so one failure never
// blanks the page. Overdue and Today use the queue board's scheduling logic.
export function useDashboardSummary() {
  const productionQueueStore = useProductionQueueStore()
  const notificationsStore = useNotificationsStore()
  const { lotsById, orderedDateByPositionId } = useProductionSchedule()

  const wipLots = ref<WipLotResponse[]>([])
  const wipLoading = ref(false)
  const summary = ref<DashboardSummaryResponse | null>(null)
  const summaryLoading = ref(false)
  const recentItems = ref<RecentCatalogueItem[]>([])

  const errored = reactive({
    productionQueue: false,
    summary: false,
    wip: false,
    recentItems: false,
  })

  const overdueOrders = ref<ProductionOrderResponse[]>([])
  const todayOrders = ref<ProductionOrderResponse[]>([])

  function rebuildSchedule(): void {
    const now = todayStart()
    const schedule = computeProductionSchedule({
      machines: productionQueueStore.machines,
      orders: productionQueueStore.orders,
      lots: [...lotsById.value.values()],
      orderedDateByPositionId: orderedDateByPositionId.value,
      now,
    })

    const overdue: ProductionOrderResponse[] = []
    const today: ProductionOrderResponse[] = []
    for (const order of productionQueueStore.orders) {
      if (order.status !== 'queued' && order.status !== 'paused') continue
      const projectedDay = schedule.get(order.id)?.start ?? now
      if (projectedDay.getTime() < now.getTime()) overdue.push(order)
      else if (projectedDay.getTime() === now.getTime()) today.push(order)
    }
    overdueOrders.value = overdue
    todayOrders.value = today
  }

  watch(() => productionQueueStore.orders, rebuildSchedule)
  watch(() => [lotsById.value, orderedDateByPositionId.value], rebuildSchedule)

  let midnightCheckInterval: ReturnType<typeof setInterval> | undefined

  async function fetchWip(): Promise<void> {
    wipLoading.value = true
    try {
      wipLots.value = await getProductionWip()
      errored.wip = false
    } catch {
      errored.wip = true
    } finally {
      wipLoading.value = false
    }
  }

  // The lot and demand counts and the recent spend come from one summary
  // the server computes, so the dashboard never reads whole lists.
  async function fetchSummary(): Promise<void> {
    summaryLoading.value = true
    try {
      summary.value = await getDashboardSummary()
      errored.summary = false
    } catch {
      errored.summary = true
    } finally {
      summaryLoading.value = false
    }
  }

  // A change to any counted list refetches the summary in the background,
  // so the tiles keep their numbers instead of flashing a loading state. A
  // failed refetch keeps the last summary; the next signal retries.
  useLiveRefresh(
    [
      LiveResource.PRODUCTION_LOTS,
      LiveResource.BOUGHT_ITEM_DEMANDS,
      LiveResource.MADE_ITEM_DEMANDS,
      LiveResource.SOURCE_ITEM_DEMANDS,
      LiveResource.ORDERS,
    ],
    async () => {
      summary.value = await getDashboardSummary()
      errored.summary = false
    },
  )

  async function fetchRecentItems(): Promise<void> {
    try {
      const [made, bought] = await Promise.all([
        getMadeItems({ order_by: 'created', order_dir: 'desc', limit: RECENT_ITEMS_LIMIT }),
        getBoughtItems({ order_by: 'created', order_dir: 'desc', limit: RECENT_ITEMS_LIMIT }),
      ])
      const merged: RecentCatalogueItem[] = [
        ...made.items.map((item) => ({
          type: 'made' as const,
          itemId: item.id,
          label: item.article_name,
          partNumber: item.part_number,
          revision: item.revision,
          created: item.created,
        })),
        ...bought.items.map((item) => ({
          type: 'bought' as const,
          itemId: item.id,
          label: item.article_name,
          partNumber: item.part_number,
          revision: null,
          created: item.created,
        })),
      ]
      recentItems.value = merged
        .sort((a, b) => new Date(b.created).getTime() - new Date(a.created).getTime())
        .slice(0, RECENT_ITEMS_LIMIT)
      errored.recentItems = false
    } catch {
      errored.recentItems = true
    }
  }

  onMounted(async () => {
    await Promise.all([
      productionQueueStore.fetchAll().then(
        () => (errored.productionQueue = false),
        () => (errored.productionQueue = true),
      ),
      fetchSummary(),
      fetchWip(),
      fetchRecentItems(),
    ])
    rebuildSchedule()
    midnightCheckInterval = setInterval(rebuildSchedule, MIDNIGHT_CHECK_INTERVAL_MS)
  })

  onUnmounted(() => {
    if (midnightCheckInterval) clearInterval(midnightCheckInterval)
  })

  const inProcessCount = computed(
    () => productionQueueStore.orders.filter((o) => o.status === 'in_progress').length,
  )
  const overdueAndTodayCount = computed(() => overdueOrders.value.length + todayOrders.value.length)
  const lotCounts = computed(() => toStatusCounts(summary.value?.lots ?? []))
  const madeDemandCounts = computed(() => toStatusCounts(summary.value?.made_demands ?? []))
  const boughtDemandCounts = computed(() => toStatusCounts(summary.value?.bought_demands ?? []))
  const sourceDemandCounts = computed(() => toStatusCounts(summary.value?.source_demands ?? []))

  const lotsCount = computed(() => sumCounts(lotCounts.value))
  const activeLotsCount = computed(
    () =>
      lotsCount.value - (lotCounts.value.completed ?? 0) - (lotCounts.value.canceled ?? 0),
  )
  // All three demand kinds count towards the demands.
  const demandsCount = computed(
    () =>
      sumCounts(madeDemandCounts.value) +
      sumCounts(boughtDemandCounts.value) +
      sumCounts(sourceDemandCounts.value),
  )
  const unreadCount = computed(() => notificationsStore.unreadCount)
  const openDemandsCount = computed(
    () =>
      (madeDemandCounts.value.open ?? 0) +
      (boughtDemandCounts.value.open ?? 0) +
      (sourceDemandCounts.value.open ?? 0),
  )

  const loading = computed(
    () => productionQueueStore.loading || summaryLoading.value || wipLoading.value,
  )

  const recentOrdersCount = computed(() => summary.value?.spend.order_count ?? 0)
  // In cents, like every other price in the app; formatted at render.
  const spentRecentlyCents = computed(() => summary.value?.spend.net_total ?? 0)
  // A running total of daily spend over the server's window, in the tenant's
  // days. Each point carries its date, since the window spans two months.
  const dailySpendSeries = computed(() => {
    let cumulative = 0
    return (summary.value?.spend.days ?? []).map((entry, i) => {
      cumulative += entry.net_total
      return { day: i + 1, cumulative, date: toLocalDayStart(entry.day) }
    })
  })

  return {
    productionQueueStore,
    madeDemandCounts,
    boughtDemandCounts,
    sourceDemandCounts,
    notificationsStore,
    wipLots,
    wipLoading,
    overdueOrders,
    todayOrders,
    recentItems,
    errored,
    loading,
    inProcessCount,
    overdueAndTodayCount,
    activeLotsCount,
    lotsCount,
    demandsCount,
    unreadCount,
    openDemandsCount,
    recentOrdersCount,
    spentRecentlyCents,
    dailySpendSeries,
  }
}
