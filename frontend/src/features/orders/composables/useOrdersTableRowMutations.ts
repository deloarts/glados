import { useRowMutationState } from '@/shared/composables/useRowMutationState'
import { useOrdersStore } from '../stores/ordersStore'

// "Mark all items ordered/requested" is a per-order bulk state change, used
// from both the row actions toolbar and the context menu.
export function useOrdersTableRowMutations() {
  const ordersStore = useOrdersStore()
  const markingAllOrdered = useRowMutationState<number>()
  const markingAllRequested = useRowMutationState<number>()

  async function markAllItemsOrdered(orderId: number): Promise<void> {
    await markingAllOrdered.run(orderId, () => ordersStore.markAllItemsOrdered(orderId))
  }

  async function markAllItemsRequested(orderId: number): Promise<void> {
    await markingAllRequested.run(orderId, () => ordersStore.markAllItemsRequested(orderId))
  }

  return { markingAllOrdered, markingAllRequested, markAllItemsOrdered, markAllItemsRequested }
}
