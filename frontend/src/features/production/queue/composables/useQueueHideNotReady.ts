import { ref, watch } from 'vue'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { safeStorage } from '@/core/utils/safeStorage'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

const STORAGE_KEY = 'glados.productionQueue.hideNotReady'

/**
 * The board's Hide Not-Ready switch, remembered per user in this browser so
 * a planner who works without the waiting orders finds them hidden again.
 * Storage is best effort through safeStorage: without it the switch simply
 * starts off.
 */
export function useQueueHideNotReady() {
  const currentUser = useCurrentUserStore()

  function storageKey(): string {
    const id = currentUser.user?.id
    return id == null ? STORAGE_KEY : `${STORAGE_KEY}.${id}`
  }

  const hideNotReady = ref(safeStorage.get(storageKey()) === 'true')

  watch(hideNotReady, (value) => {
    safeStorage.set(storageKey(), String(value))
  })

  return { hideNotReady }
}

/**
 * Whether the order waits in the queue but Start would be refused right now,
 * by the backend's own verdict (no machine, missing material, an earlier
 * step still open). Running and finished orders are never "not ready".
 */
export function isNotReady(order: ProductionOrderResponse): boolean {
  return (order.status === 'queued' || order.status === 'paused') && !order.can_start
}
