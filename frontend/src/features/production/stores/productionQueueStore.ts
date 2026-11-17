import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { fetchAllPages } from '@/core/api/fetchAllPages'

import { getProductionMachines } from '@/features/production-machines'
import { getMachinePools } from '@/features/production-machines'
import { getProductionOrders } from '../api/getProductionOrders'
import { updateProductionOrder } from '../api/updateProductionOrder'
import { splitProductionOrder } from '../api/splitProductionOrder'
import { mergeProductionOrders } from '../api/mergeProductionOrders'
import { reorderProductionOrders } from '../api/reorderProductionOrders'
import { reorderProductionOrdersByPool } from '../api/reorderProductionOrdersByPool'
import { reassignProductionOrderMachine } from '../api/reassignProductionOrderMachine'
import { startProductionOrder } from '../api/startProductionOrder'
import { pauseProductionOrder } from '../api/pauseProductionOrder'
import { cancelProductionOrder } from '../api/cancelProductionOrder'
import { recordProductionOrderCompletion } from '../api/recordProductionOrderCompletion'
import { recordManufacturingAssessment } from '../api/recordManufacturingAssessment'
import { getOperators } from '../api/getOperators'
import {
  FINISHED_ORDER_WINDOW_MS,
  FINISHED_PRODUCTION_ORDER_STATUSES,
  OPEN_PRODUCTION_ORDER_STATUSES,
} from '../utils/productionOrderStatus'

import type { ProductionMachineResponse } from '@/features/production-machines'
import type { MachinePoolResponse } from '@/features/production-machines'
import type {
  MergeProductionOrdersRequest,
  PauseProductionOrderRequest,
  ReassignProductionOrderMachineRequest,
  RecordManufacturingAssessmentRequest,
  RecordProductionOrderCompletionRequest,
  SplitProductionOrderRequest,
  StartProductionOrderRequest,
  UpdateProductionOrderRequest,
} from '../types/productionOrdersRequest'
import type {
  ManufacturingAssessmentResponse,
  ProductionOrderResponse,
} from '../types/productionOrdersResponse'
import type { Operator } from '../types/operatorsResponse'

export const useProductionQueueStore = defineStore('productionQueue', () => {
  const machines = ref<ProductionMachineResponse[]>([])
  const machinePools = ref<MachinePoolResponse[]>([])
  const orders = ref<ProductionOrderResponse[]>([])
  const operators = ref<Operator[]>([])
  const loading = ref(false)
  // A live-signal re-sync. Not `loading`, which would tear down views gated
  // on their first-load skeleton.
  const refreshing = ref(false)
  const mutating = ref(false)

  const ordersByMachine = computed(() => {
    const grouped = new Map<number | null, ProductionOrderResponse[]>()
    grouped.set(null, [])
    for (const machine of machines.value) {
      grouped.set(machine.id, [])
    }
    for (const order of orders.value) {
      const list = grouped.get(order.machine_id)
      if (list) {
        list.push(order)
      } else {
        grouped.set(order.machine_id, [order])
      }
    }
    for (const list of grouped.values()) {
      list.sort((a, b) => a.queue_sequence - b.queue_sequence)
    }
    return grouped
  })

  // Pool-assigned orders without a machine; disjoint from ordersByMachine.
  const ordersByPool = computed(() => {
    const grouped = new Map<number, ProductionOrderResponse[]>()
    for (const pool of machinePools.value) {
      grouped.set(pool.id, [])
    }
    for (const order of orders.value) {
      if (order.machine_id !== null || order.machine_pool_id == null) continue
      const list = grouped.get(order.machine_pool_id)
      if (list) {
        list.push(order)
      } else {
        grouped.set(order.machine_pool_id, [order])
      }
    }
    for (const list of grouped.values()) {
      list.sort((a, b) => a.queue_sequence - b.queue_sequence)
    }
    return grouped
  })

  async function fetchMachines(): Promise<void> {
    const response = await getProductionMachines({ limit: API_MAX_PAGE_SIZE })
    machines.value = response.items
  }

  async function fetchMachinePools(): Promise<void> {
    const response = await getMachinePools({ limit: API_MAX_PAGE_SIZE })
    machinePools.value = response.items
  }

  // Only the latest fetch may assign, so overlapping live refreshes never
  // put an older answer back.
  let ordersRequestId = 0

  /**
   * Every open order, page by page, plus the finished ones changed inside the
   * board's window. Open work is never cut off however many orders the shop
   * has made, and older finished work, which no view shows, is not loaded.
   */
  async function fetchOrders(): Promise<void> {
    const requestId = ++ordersRequestId
    const changedFrom = new Date(Date.now() - FINISHED_ORDER_WINDOW_MS).toISOString()
    const [open, finished] = await Promise.all([
      fetchAllPages((page) =>
        getProductionOrders({ ...page, statuses: OPEN_PRODUCTION_ORDER_STATUSES }),
      ),
      fetchAllPages((page) =>
        getProductionOrders({
          ...page,
          statuses: FINISHED_PRODUCTION_ORDER_STATUSES,
          changed_from: changedFrom,
        }),
      ),
    ])
    if (requestId !== ordersRequestId) return
    // An order that finished between the two requests is in both answers;
    // the finished one is the later state.
    const byId = new Map(open.map((order) => [order.id, order]))
    for (const order of finished) byId.set(order.id, order)
    orders.value = [...byId.values()]
  }

  async function fetchOperators(): Promise<void> {
    operators.value = await getOperators()
  }

  async function fetchAll(): Promise<void> {
    loading.value = true
    try {
      await Promise.all([fetchMachines(), fetchMachinePools(), fetchOrders(), fetchOperators()])
    } finally {
      loading.value = false
    }
  }

  /**
   * Re-sync from a live signal, refetching only the resource that signalled.
   * Operators change on their own resource and are never refetched here.
   */
  async function refreshLive(resources: {
    machines?: boolean
    pools?: boolean
    orders?: boolean
  }): Promise<void> {
    const pending: Promise<void>[] = []
    if (resources.machines) pending.push(fetchMachines())
    if (resources.pools) pending.push(fetchMachinePools())
    if (resources.orders) pending.push(fetchOrders())
    if (pending.length === 0) return

    refreshing.value = true
    try {
      await Promise.all(pending)
    } finally {
      refreshing.value = false
    }
  }

  async function withMutation<T>(
    action: () => Promise<T>,
    applyResult: (result: T) => void,
  ): Promise<T> {
    mutating.value = true
    try {
      const result = await action()
      applyResult(result)
      return result
    } finally {
      mutating.value = false
    }
  }

  // Merges response orders by id instead of refetching. Always assigns a new
  // array, because consumers use a shallow watch that ignores in-place
  // mutation. Entries without a numeric id are dropped.
  function applyOrders(updated: ProductionOrderResponse[]): void {
    if (!Array.isArray(updated)) return
    const valid = updated.filter((o) => typeof o?.id === 'number')
    if (valid.length === 0) return

    const byId = new Map(valid.map((o) => [o.id, o]))
    const merged = orders.value.map((o) => byId.get(o.id) ?? o)
    const existingIds = new Set(orders.value.map((o) => o.id))
    const created = valid.filter((o) => !existingIds.has(o.id))
    orders.value = created.length > 0 ? [...merged, ...created] : merged
  }

  function applyOrder(updated: ProductionOrderResponse): void {
    applyOrders([updated])
  }

  // An edit or a cancel carries the order's edit version as the caller
  // showed it, so a concurrent change answers 409.
  async function update(id: number, payload: UpdateProductionOrderRequest): Promise<void> {
    await withMutation(() => updateProductionOrder(id, payload), applyOrder)
  }

  async function togglePinned(order: ProductionOrderResponse): Promise<void> {
    await once(`pin:${order.id}`, () =>
      update(order.id, { pinned: !order.pinned, expected_edit_version: order.edit_version }),
    )
  }

  async function split(id: number, payload: SplitProductionOrderRequest): Promise<void> {
    // The response holds every touched order, so no refetch is needed.
    await withMutation(() => splitProductionOrder(id, payload), applyOrders)
  }

  async function merge(payload: MergeProductionOrdersRequest): Promise<void> {
    // Only the surviving order returns; the others were canceled, so every
    // requested id except the survivor is marked canceled locally.
    await withMutation(
      () => mergeProductionOrders(payload),
      (keeper) => {
        if (typeof keeper?.id !== 'number') return
        const absorbedIds = new Set(
          payload.production_order_ids.filter((id) => id !== keeper.id),
        )
        orders.value = orders.value.map((o): ProductionOrderResponse => {
          if (o.id === keeper.id) return keeper
          if (absorbedIds.has(o.id)) return { ...o, status: 'canceled', quantity: 0 }
          return o
        })
      },
    )
  }

  async function reorder(
    machineId: number | null,
    orderedProductionOrderIds: number[],
  ): Promise<void> {
    // Only requested orders are renumbered, so merging the response is
    // complete.
    await withMutation(
      () => reorderProductionOrders(machineId, orderedProductionOrderIds),
      applyOrders,
    )
  }

  // `reorder` for a pool's unresolved orders.
  async function reorderPool(
    poolId: number,
    orderedProductionOrderIds: number[],
  ): Promise<void> {
    await withMutation(
      () => reorderProductionOrdersByPool(poolId, orderedProductionOrderIds),
      applyOrders,
    )
  }

  // Targets a machine (null for unassigned) or, with `{ machinePoolId }`,
  // a pool.
  async function reassignMachine(
    id: number,
    target: number | null | { machinePoolId: number },
  ): Promise<void> {
    const payload: ReassignProductionOrderMachineRequest =
      typeof target === 'object' && target !== null
        ? { machine_pool_id: target.machinePoolId }
        : { machine_id: target }
    // Only this order changes.
    await withMutation(() => reassignProductionOrderMachine(id, payload), applyOrder)
  }

  // A one-click card action (start, resume, cancel, pin) already running for
  // an order is not sent again; a second click joins the first request, so a
  // double click cannot fire the transition twice.
  const actionsInFlight = new Map<string, Promise<unknown>>()

  function once<T>(key: string, action: () => Promise<T>): Promise<T> {
    const running = actionsInFlight.get(key)
    if (running) return running as Promise<T>
    const started = action().finally(() => actionsInFlight.delete(key))
    actionsInFlight.set(key, started)
    return started
  }

  async function start(id: number, payload: StartProductionOrderRequest = {}): Promise<void> {
    await once(`start:${id}`, () => withMutation(() => startProductionOrder(id, payload), applyOrder))
  }

  async function pause(id: number, payload: PauseProductionOrderRequest = {}): Promise<void> {
    await withMutation(() => pauseProductionOrder(id, payload), applyOrder)
  }

  async function cancel(id: number, editVersion: number, reason?: string | null): Promise<void> {
    await once(`cancel:${id}`, () =>
      withMutation(
        () => cancelProductionOrder(id, { reason, expected_edit_version: editVersion }),
        applyOrder,
      ),
    )
  }

  async function recordCompletion(
    id: number,
    payload: RecordProductionOrderCompletionRequest,
  ): Promise<ProductionOrderResponse> {
    return withMutation(() => recordProductionOrderCompletion(id, payload), applyOrder)
  }

  async function recordAssessment(
    id: number,
    payload: RecordManufacturingAssessmentRequest,
  ): Promise<ManufacturingAssessmentResponse> {
    // The order itself is unchanged, so only its assessment is patched.
    return withMutation(
      () => recordManufacturingAssessment(id, payload),
      (assessment) => {
        if (typeof assessment?.production_order_id !== 'number') return
        orders.value = orders.value.map((o): ProductionOrderResponse =>
          o.id === assessment.production_order_id ? { ...o, assessment } : o,
        )
      },
    )
  }

  return {
    machines,
    machinePools,
    orders,
    operators,
    loading,
    refreshing,
    mutating,
    ordersByMachine,
    ordersByPool,
    fetchMachines,
    fetchMachinePools,
    fetchOrders,
    fetchOperators,
    fetchAll,
    refreshLive,
    update,
    togglePinned,
    split,
    merge,
    reorder,
    reorderPool,
    reassignMachine,
    start,
    pause,
    cancel,
    recordCompletion,
    recordAssessment,
  }
})
