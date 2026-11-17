import { reactive, watch, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { parseBackendTimestamp, startOfDay, toDateKey } from '@/core/utils/dates'
import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { FINISHED_ORDER_WINDOW_MS, isProductionOrderLocked } from '../../utils/productionOrderStatus'
import { computeProductionSchedule } from '../../utils/productionPlanningTasks'
import { poolColumnKey } from '../../utils/queueColumnRouting'
import { fullQueueIdsForColumn } from '../../utils/queueReorderPayload'
import { isNotReady } from './useQueueHideNotReady'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'
import type { LotResponse } from '../../types/productionLotsResponse'
import type { QueueColumnTarget } from './useQueueBoardColumns'

// The fields read from the SortableJS move event vuedraggable forwards to
// `:move`; vuedraggable types it as `any`.
interface DraggableMoveEvent {
  draggedContext: { element: ProductionOrderResponse; index: number }
  relatedContext: { element?: ProductionOrderResponse; index: number }
}

// A same-column reorder yields `moved`. A cross-column drop yields `added`
// on the target and `removed` on the source; the target's `added` covers
// the whole transition, so `removed` is ignored.
interface DraggableChangeEvent {
  added?: { element: ProductionOrderResponse; newIndex: number }
  removed?: { element: ProductionOrderResponse; oldIndex: number }
  moved?: { element: ProductionOrderResponse; newIndex: number; oldIndex: number }
}

interface QueueOtherGroups {
  active: ProductionOrderResponse[]
  terminal: ProductionOrderResponse[]
}

export interface QueueBoardGroupsOptions {
  todayStart: Ref<Date>
  rangeDays: Ref<Date[]>
  dayKeys: Ref<string[]>
  showCompleted: Ref<boolean>
  hideNotReady: Ref<boolean>
  lotsById: Ref<Map<number, LotResponse>>
  orderedDateByPositionId: Ref<Map<number, string | null>>
  orderColumnKeyFor: (order: ProductionOrderResponse) => string
}

export const OVERDUE_KEY = 'overdue'

function isWithinTerminalWindow(order: ProductionOrderResponse): boolean {
  const timestamp = order.changed ?? order.created
  return Date.now() - parseBackendTimestamp(timestamp).getTime() <= FINISHED_ORDER_WINDOW_MS
}

/**
 * Order groups of the production queue board and the drag and drop that
 * reorders or reassigns them. Each column holds an Overdue group and one
 * group per day in the range for queued and paused work, plus read-only
 * active and terminal lists.
 */
export function useQueueBoardGroups(options: QueueBoardGroupsOptions) {
  const { t } = useI18n()
  const { withErrorToast } = useErrorToast()
  const store = useProductionQueueStore()
  const { todayStart, rangeDays, dayKeys, showCompleted, hideNotReady } = options

  // vuedraggable mutates these arrays through v-model, so they are working
  // copies rebuilt from the store, keyed `${columnKey}|${dayKey}` where the
  // day is OVERDUE_KEY or a YYYY-MM-DD inside the range.
  const localGroups = reactive<Record<string, ProductionOrderResponse[]>>({})
  const otherOrders = reactive<Record<string, QueueOtherGroups>>({})

  function groupKey(column: string, day: string): string {
    return `${column}|${day}`
  }

  function groupOrders(column: string, day: string): ProductionOrderResponse[] {
    return localGroups[groupKey(column, day)] ?? []
  }

  // Hide Not-Ready only hides the cards: they stay in the group arrays, so
  // a drag between the visible cards still sends the whole group in its
  // board order and the hidden ones keep their places in the queue.
  function isHidden(order: ProductionOrderResponse): boolean {
    return hideNotReady.value && isNotReady(order)
  }

  function visibleCount(column: string, day: string): number {
    return groupOrders(column, day).filter((order) => !isHidden(order)).length
  }

  function columnCount(column: string): number {
    const groups = otherOrders[column]
    const dayTotal = [OVERDUE_KEY, ...dayKeys.value].reduce(
      (sum, day) => sum + visibleCount(column, day),
      0,
    )
    return (
      dayTotal +
      (groups?.active.length ?? 0) +
      (showCompleted.value ? (groups?.terminal.length ?? 0) : 0)
    )
  }

  // A live signal landing mid-drag would swap the array SortableJS is
  // holding, so rebuilds are deferred to drag end.
  let dragging = false
  let rebuildPending = false
  let dropHandled = false

  function rebuildLocalOrders(): void {
    if (dragging) {
      rebuildPending = true
      return
    }

    const now = todayStart.value
    const schedule = computeProductionSchedule({
      machines: store.machines,
      orders: store.orders,
      lots: [...options.lotsById.value.values()],
      orderedDateByPositionId: options.orderedDateByPositionId.value,
      now,
    })

    const columnKeys: string[] = [
      'unassigned',
      'manual',
      'inspection',
      ...store.machinePools.map((p) => poolColumnKey(p.id)),
      ...store.machines.map((m) => String(m.id)),
    ]
    const ordersByKey = new Map<string, ProductionOrderResponse[]>()
    for (const key of columnKeys) ordersByKey.set(key, [])
    for (const order of store.orders) {
      const key = options.orderColumnKeyFor(order)
      if (!ordersByKey.has(key)) ordersByKey.set(key, [])
      ordersByKey.get(key)!.push(order)
    }
    for (const list of ordersByKey.values()) {
      list.sort((a, b) => a.queue_sequence - b.queue_sequence)
    }

    const days = rangeDays.value
    const rangeStart = (days[0] ?? now).getTime()
    const rangeEnd = (days[days.length - 1] ?? now).getTime()
    const liveKeys = new Set<string>()

    for (const key of columnKeys) {
      const machineOrders = ordersByKey.get(key) ?? []
      const active: ProductionOrderResponse[] = []
      const terminal: ProductionOrderResponse[] = []
      const byDay = new Map<string, ProductionOrderResponse[]>()
      byDay.set(OVERDUE_KEY, [])
      for (const day of dayKeys.value) byDay.set(day, [])

      for (const order of machineOrders) {
        if (order.status === 'in_progress') {
          active.push(order)
        } else if (order.status === 'queued' || order.status === 'paused') {
          // Bucketed by projected start day. Work projected before the range
          // collapses into Overdue; work after it stays off the board.
          const projectedDay = startOfDay(schedule.get(order.id)?.start ?? now)
          const projected = projectedDay.getTime()
          if (projected < rangeStart) byDay.get(OVERDUE_KEY)!.push(order)
          else if (projected <= rangeEnd) byDay.get(toDateKey(projectedDay))?.push(order)
        } else if (isWithinTerminalWindow(order)) {
          terminal.push(order)
        }
      }

      for (const [day, orders] of byDay) {
        const key2 = groupKey(key, day)
        localGroups[key2] = orders
        liveKeys.add(key2)
      }
      otherOrders[key] = { active, terminal }
    }

    // Drop groups of days that left the range or of removed machines.
    for (const key of Object.keys(localGroups)) {
      if (!liveKeys.has(key)) delete localGroups[key]
    }
  }

  watch(() => store.orders, rebuildLocalOrders, { deep: false })
  watch(() => store.machines, rebuildLocalOrders)
  watch(() => [options.lotsById.value, options.orderedDateByPositionId.value], rebuildLocalOrders)
  watch(dayKeys, rebuildLocalOrders)

  function onDragStart(): void {
    dragging = true
    dropHandled = false
  }

  function onDragEnd(): void {
    dragging = false
    if (!rebuildPending) return
    rebuildPending = false
    // SortableJS emits change before end, so a handled drop already has a
    // mutation in flight whose refetch rebuilds the lists. Rebuilding here
    // would flash the pre-drop arrangement first.
    if (!dropHandled) rebuildLocalOrders()
  }

  function checkMove(evt: DraggableMoveEvent): boolean {
    if (isProductionOrderLocked(evt.draggedContext.element)) return false
    const related = evt.relatedContext.element
    if (related && isProductionOrderLocked(related)) return false
    return true
  }

  // The reorder endpoint renumbers only the ids it receives, so the payload
  // carries the visible groups in board order followed by the column's
  // hidden out-of-range orders, which keep their relative order.
  function queueReorderIdsForColumn(column: QueueColumnTarget): number[] {
    const visibleOrders = [OVERDUE_KEY, ...dayKeys.value].flatMap((day) =>
      groupOrders(column.key, day),
    )

    let futureOrders: ProductionOrderResponse[]
    switch (column.kind) {
      case 'pool':
        futureOrders = store.ordersByPool.get(column.id!) ?? []
        break
      case 'unassigned':
        // The machine_id=null bucket shares its sequence space with manual
        // and inspection orders, but pool-assigned orders have their own.
        futureOrders = (store.ordersByMachine.get(null) ?? []).filter(
          (o) => o.machine_pool_id == null,
        )
        break
      case 'machine':
        futureOrders = store.ordersByMachine.get(column.id) ?? []
        break
      default:
        // Manual and inspection columns are static and never reordered.
        futureOrders = []
    }

    return fullQueueIdsForColumn(visibleOrders, futureOrders)
  }

  async function submitReorder(column: QueueColumnTarget, orderedIds: number[]): Promise<void> {
    if (column.kind === 'pool') {
      await store.reorderPool(column.id!, orderedIds)
    } else {
      await store.reorder(column.id, orderedIds)
    }
  }

  async function onGroupReorder(column: QueueColumnTarget): Promise<void> {
    const orderedIds = queueReorderIdsForColumn(column)
    if (orderedIds.length === 0) return

    const succeeded = await withErrorToast(
      async () => {
        await submitReorder(column, orderedIds)
        return true
      },
      { summary: t('productionQueue.card.reorderError') },
    )
    // Bounce back to the last known-good server order on failure.
    if (!succeeded) rebuildLocalOrders()
  }

  async function onGroupCrossColumnDrop(column: QueueColumnTarget, orderId: number): Promise<void> {
    // Captured before the reassign, whose refetch rebuilds the groups.
    const orderedIds = queueReorderIdsForColumn(column)

    const succeeded = await withErrorToast(
      async () => {
        // A pool column assigns the pool and the backend resolves a machine
        // later; a machine or unassigned column sets or clears it directly.
        if (column.kind === 'pool') {
          await store.reassignMachine(orderId, { machinePoolId: column.id! })
        } else {
          await store.reassignMachine(orderId, column.id)
        }
        if (orderedIds.length > 0) {
          await submitReorder(column, orderedIds)
        }
        return true
      },
      { summary: t('productionQueue.card.reassignError') },
    )
    if (!succeeded) rebuildLocalOrders()
  }

  // Each group has its own Sortable group name, so a drop only ever lands
  // in the same group of the same or another column.
  async function onGroupChange(column: QueueColumnTarget, evt: DraggableChangeEvent): Promise<void> {
    dropHandled = true
    if (evt.added) {
      await onGroupCrossColumnDrop(column, evt.added.element.id)
      return
    }
    if (evt.moved) {
      await onGroupReorder(column)
    }
  }

  return {
    localGroups,
    otherOrders,
    groupKey,
    groupOrders,
    isHidden,
    visibleCount,
    columnCount,
    rebuildLocalOrders,
    onDragStart,
    onDragEnd,
    checkMove,
    onGroupChange,
  }
}
