import { onScopeDispose, ref, watch } from 'vue'

import { getOrder } from '../api/getOrder'
import { useLiveStore } from '@/core/realtime/liveStore'
import { LiveResource } from '@/core/realtime/resources'
import type { OrderResponse } from '../types/ordersResponse'
import { apiErrorStatus } from '@/core/utils/errors'

/**
 * The single order behind /procurement/orders/:id. It bypasses
 * useOrdersStore, whose mutations refresh only rows in its list, so the page
 * owns its record and reloads itself.
 */
export function useOrderDetail(orderId: number) {
  const live = useLiveStore()

  const order = ref<OrderResponse | null>(null)
  const loading = ref(true)
  const notFound = ref(false)
  const loadError = ref(false)

  /**
   * quiet skips the loading flag for background refetches, so a live signal
   * never flashes a spinner.
   */
  async function reload({ quiet = false }: { quiet?: boolean } = {}): Promise<void> {
    if (!quiet) loading.value = true
    try {
      order.value = await getOrder(orderId)
      notFound.value = false
      loadError.value = false
    } catch (e) {
      if (apiErrorStatus(e) === 404) {
        order.value = null
        notFound.value = true
        loadError.value = false
      } else {
        loadError.value = true
      }
    } finally {
      if (!quiet) loading.value = false
    }
  }

  const unsubscribe = live.on(LiveResource.ORDERS, (signal) => {
    if (signal.id !== orderId) return
    if (signal.action === 'deleted') {
      order.value = null
      notFound.value = true
      return
    }
    void reload({ quiet: true })
  })

  // Recovers whatever was missed while disconnected.
  watch(
    () => live.reconnectCount,
    () => void reload({ quiet: true }),
  )

  onScopeDispose(unsubscribe)

  // Starts during setup, so the request is in flight right away.
  void reload()

  return { order, loading, notFound, loadError, reload }
}
