import { computed, onMounted, onUnmounted, ref } from 'vue'

import { usePermissions } from '@/core/composables/usePermissions'
import { useProductionPlanning } from '@/core/composables/useProductionPlanning'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useProductionQueueStore } from '@/features/production'
import { useProductionSchedule } from '@/features/production'
import { computeProductionSchedule } from '@/features/production'
import { useMadeItemLabel } from '@/features/made-items'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { getTodoSources } from '../api/getTodoSources'
import { buildTodoTasks, sortTodoTasks } from '../utils/buildTodoTasks'

import type { OrderResponse } from '@/features/orders'
import type { BoughtItemDemandResponse } from '@/features/bought-items'
import type { MadeItemDemandResponse } from '@/features/made-items'
import type { SourceItemDemandResponse } from '@/features/source-items'
import type { LotSummaryResponse } from '@/features/production'
import type { MeetingTodoSourceResponse } from '../types/todoSourcesResponse'
import {
  TODO_CATEGORIES,
  type TodoBucket,
  type TodoCategory,
  type TodoTask,
} from '../types/todoTask'

const MIDNIGHT_CHECK_INTERVAL_MS = 5 * 60 * 1000

// Derives the team-wide task list from the rows the server filters to the
// open work: every order, demand and lot that can give a task, in the shapes
// of their list endpoints. Kept out of the shared list stores, whose full
// list views would otherwise hold the wrong rows.
export function useTodoTasks() {
  const { hasPermission } = usePermissions()
  const { productionPlanningEnabled } = useProductionPlanning()
  const hostStore = useHostStore()
  const { format: madeItemLabel } = useMadeItemLabel()
  const productionQueueStore = useProductionQueueStore()
  const { lotsById, orderedDateByPositionId } = useProductionSchedule()

  const orders = ref<OrderResponse[]>([])
  const boughtDemands = ref<BoughtItemDemandResponse[]>([])
  const madeDemands = ref<MadeItemDemandResponse[]>([])
  const sourceDemands = ref<SourceItemDemandResponse[]>([])
  const lots = ref<LotSummaryResponse[]>([])
  const meetingTodos = ref<MeetingTodoSourceResponse[]>([])
  const loading = ref(false)
  const errored = ref(false)
  const showAll = ref(false)
  const selectedCategories = ref<TodoCategory[]>([...TODO_CATEGORIES])
  // Bumped periodically so the buckets recompute after midnight even when no
  // data changed.
  const clockTick = ref(0)

  async function load(): Promise<void> {
    // The dashboard calls this too; with todos switched off it shows no task
    // tiles, so there is nothing to fetch.
    if (!hostStore.todosEnabled) return
    const sources = await getTodoSources({ include_lots: productionPlanningEnabled.value })
    orders.value = sources.orders
    boughtDemands.value = sources.bought_demands
    madeDemands.value = sources.made_demands
    sourceDemands.value = sources.source_demands
    lots.value = sources.lots
    meetingTodos.value = sources.meeting_todos
    errored.value = false
  }

  async function refresh(): Promise<void> {
    loading.value = true
    try {
      await load()
    } catch {
      errored.value = true
    } finally {
      loading.value = false
    }
  }

  // A change to any source list reloads the rows in the background, so the
  // list stays in place instead of showing the loading state. A failed
  // reload keeps the last rows; the next signal retries.
  useLiveRefresh(
    [
      LiveResource.ORDERS,
      LiveResource.BOUGHT_ITEM_DEMANDS,
      LiveResource.MADE_ITEM_DEMANDS,
      LiveResource.SOURCE_ITEM_DEMANDS,
      LiveResource.PRODUCTION_LOTS,
      LiveResource.MEETINGS,
    ],
    load,
  )

  let midnightCheckInterval: ReturnType<typeof setInterval> | undefined

  onMounted(async () => {
    await Promise.all([
      refresh(),
      productionPlanningEnabled.value
        ? productionQueueStore.fetchAll().catch(() => (errored.value = true))
        : Promise.resolve(),
    ])
    midnightCheckInterval = setInterval(() => clockTick.value++, MIDNIGHT_CHECK_INTERVAL_MS)
  })

  onUnmounted(() => {
    if (midnightCheckInterval) clearInterval(midnightCheckInterval)
  })

  const allTasks = computed<TodoTask[]>(() => {
    void clockTick.value
    const now = new Date()
    const productionSchedule = computeProductionSchedule({
      machines: productionQueueStore.machines,
      orders: productionQueueStore.orders,
      lots: [...lotsById.value.values()],
      orderedDateByPositionId: orderedDateByPositionId.value,
      now,
    })

    const built = buildTodoTasks({
      orders: orders.value,
      boughtDemands: boughtDemands.value,
      madeDemands: madeDemands.value,
      sourceDemands: sourceDemands.value,
      // Empty inputs rather than a later filter, so the category counts stay
      // honest when Production Planning is off.
      productionOrders: productionPlanningEnabled.value ? productionQueueStore.orders : [],
      productionSchedule,
      lots: productionPlanningEnabled.value ? lots.value : [],
      meetingTodos: meetingTodos.value,
      madeItemLabel,
      now,
    })

    // Team-wide, but only tasks the user has permission to act on.
    return sortTodoTasks(built.filter((task) => task.permission === null || hasPermission(task.permission)))
  })

  // Basis for the per-category counts, before the category filter applies.
  const importantFiltered = computed(() =>
    showAll.value ? allTasks.value : allTasks.value.filter((task) => task.important),
  )

  const visibleTasks = computed(() =>
    importantFiltered.value.filter((task) => selectedCategories.value.includes(task.category)),
  )

  const hiddenCount = computed(() => allTasks.value.length - importantFiltered.value.length)

  const categoryCounts = computed<Record<TodoCategory, number>>(() => {
    const counts = { procurement: 0, shop_floor: 0, planning: 0, meetings: 0 }
    for (const task of importantFiltered.value) counts[task.category]++
    return counts
  })

  function toggleCategory(category: TodoCategory): void {
    selectedCategories.value = selectedCategories.value.includes(category)
      ? selectedCategories.value.filter((c) => c !== category)
      : [...selectedCategories.value, category]
  }

  function resetCategories(): void {
    selectedCategories.value = [...TODO_CATEGORIES]
  }

  function tasksIn(bucket: TodoBucket): TodoTask[] {
    return visibleTasks.value.filter((task) => task.bucket === bucket)
  }

  const overdue = computed(() => tasksIn('overdue'))
  const today = computed(() => tasksIn('today'))
  const week = computed(() => tasksIn('week'))
  const blockers = computed(() => tasksIn('blockers'))
  const dueNowCount = computed(() => overdue.value.length + today.value.length)

  return {
    allTasks,
    visibleTasks,
    hiddenCount,
    showAll,
    selectedCategories,
    categoryCounts,
    toggleCategory,
    resetCategories,
    overdue,
    today,
    week,
    blockers,
    dueNowCount,
    loading,
    errored,
    refresh,
  }
}
