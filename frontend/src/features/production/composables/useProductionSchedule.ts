import { computed, onMounted, ref, watch } from 'vue'

import { useProductionQueueStore } from '../stores/productionQueueStore'
import { getLot } from '../api/getLot'
import { getOrdersByIds } from '@/features/orders'
import { isActiveProductionOrder } from '../utils/productionPlanningTasks'
import type { LotResponse } from '../types/productionLotsResponse'

// Lot detail for every lot referenced by an active order, plus each external
// position's ordered_date from its order. Shared by the planning gantt and the
// queue board so both agree on the schedule.
//
// Lots are fetched one by one because the list endpoint's summary positions
// lack sequence, steps and supplier_name, which the schedule needs. Orders
// are batched.
export function useProductionSchedule() {
  const store = useProductionQueueStore()

  const lotsById = ref(new Map<number, LotResponse>())
  const orderedDateByPositionId = ref(new Map<number, string | null>())
  const loading = ref(false)

  // Bumped per call, so a refresh that finds a newer one started after an
  // await drops its stale result.
  let refreshToken = 0

  async function refresh(): Promise<void> {
    const token = ++refreshToken
    const lotIds = [
      ...new Set(store.orders.filter(isActiveProductionOrder).map((order) => order.lot_id)),
    ]
    loading.value = true
    try {
      const fetched = await Promise.all(lotIds.map((id) => getLot(id)))
      if (token !== refreshToken) return

      lotsById.value = new Map(fetched.map((lot) => [lot.id, lot]))

      const externalPositions = fetched.flatMap((lot) =>
        (lot.positions ?? []).filter((p) => p.kind === 'external'),
      )
      const orderIds = [
        ...new Set(
          externalPositions.map((p) => p.order_id).filter((id): id is number => id != null),
        ),
      ]
      const orders = await getOrdersByIds(orderIds)
      if (token !== refreshToken) return

      const orderById = new Map(orders.map((o) => [o.id, o]))

      const nextOrderedDates = new Map<number, string | null>()
      for (const position of externalPositions) {
        const order = position.order_id != null ? orderById.get(position.order_id) : undefined
        const item = order?.items?.find((i) => i.lot_position_id === position.id)
        nextOrderedDates.set(position.id, item?.ordered_date ?? order?.ordered_date ?? null)
      }
      orderedDateByPositionId.value = nextOrderedDates
    } finally {
      if (token === refreshToken) loading.value = false
    }
  }

  onMounted(refresh)
  watch(() => store.orders, refresh)

  // Whether every active order's lot is loaded. Until then a card cannot
  // name its position, its method or its column.
  const complete = computed(() =>
    store.orders.filter(isActiveProductionOrder).every((order) => lotsById.value.has(order.lot_id)),
  )

  return { lotsById, orderedDateByPositionId, loading, complete, refresh }
}
