import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useConfetti } from '@/core/composables/useConfetti'
import { useSequencedFetch } from '@/core/composables/useSequencedFetch'

import { createOrder } from '../api/createOrder'
import { getOrder } from '../api/getOrder'
import { getOrders } from '../api/getOrders'
import { updateOrder } from '../api/updateOrder'
import { setOrderExtraCosts } from '../api/setOrderExtraCosts'
import { submitOrder } from '../api/submitOrder'
import { requestOrder } from '../api/requestOrder'
import { cancelOrder } from '../api/cancelOrder'
import { cancelOrderItem } from '../api/cancelOrderItem'
import { closeOrderItemShort } from '../api/closeOrderItemShort'
import { reopenOrderItem } from '../api/reopenOrderItem'
import { correctOrderItemDelivery } from '../api/correctOrderItemDelivery'
import { createOrderItem } from '../api/createOrderItem'
import { deliverOrderItem } from '../api/deliverOrderItem'
import { deliverAllOrderItems } from '../api/deliverAllOrderItems'
import { markOrderItemOrdered } from '../api/markOrderItemOrdered'
import { markAllOrderItemsOrdered } from '../api/markAllOrderItemsOrdered'
import { markOrderItemRequested } from '../api/markOrderItemRequested'
import { markAllOrderItemsRequested } from '../api/markAllOrderItemsRequested'
import { markOrderItemReadyForPickup } from '../api/markOrderItemReadyForPickup'
import { moveOrderItem } from '../api/moveOrderItem'
import { removeOrderItem } from '../api/removeOrderItem'
import { updateOrderItem } from '../api/updateOrderItem'

import type {
  OrderCreateRequest,
  OrderExtraCostsUpdateRequest,
  OrderFilterParams,
  OrderUpdateRequest,
} from '../types/ordersRequest'
import type {
  CorrectDeliveryRequest,
  DeliveryRejectionRequest,
  OrderItemCreateRequest,
  OrderItemRejectionRequest,
  OrderItemUpdateRequest,
} from '../types/ordersRequest'
import type { OrderItemResponse, OrderResponse, OrderStatus } from '../types/ordersResponse'

export const useOrdersStore = defineStore('orders', () => {
  const { celebrate } = useConfetti()

  const { loading, error, run } = useSequencedFetch(getOrders)
  const items = ref<OrderResponse[]>([])
  const total = ref(0)
  const refreshTrigger = ref(0)

  async function refresh(params?: OrderFilterParams): Promise<void> {
    const response = await run(params)
    if (!response) return

    items.value = response.items
    total.value = response.total
  }

  function triggerRefresh(): void {
    refreshTrigger.value++
  }

  function clear(): void {
    items.value = []
    total.value = 0
  }

  async function create(payload: OrderCreateRequest): Promise<OrderResponse> {
    return await createOrder(payload)
  }

  // An edit or an irreversible action carries the edit version of the order
  // or the line as the caller showed it, so a concurrent change answers 409
  // instead of being overwritten.
  async function update(id: number, payload: OrderUpdateRequest): Promise<OrderResponse> {
    await updateOrder(id, payload)
    await refreshOrder(id)
    return items.value.find((o) => o.id === id)!
  }

  async function setExtraCosts(
    id: number,
    payload: OrderExtraCostsUpdateRequest,
  ): Promise<OrderResponse> {
    const saved = await setOrderExtraCosts(id, payload)
    await refreshOrder(id)
    return saved
  }

  async function submit(id: number): Promise<void> {
    await submitOrder(id)
    await refreshOrder(id)
  }

  async function request(id: number): Promise<void> {
    await requestOrder(id)
    await refreshOrder(id)
  }

  async function cancel(id: number, editVersion: number): Promise<void> {
    await cancelOrder(id, editVersion)
    await refreshOrder(id)
  }

  async function addItem(
    orderId: number,
    payload: Omit<OrderItemCreateRequest, 'order_id'>,
  ): Promise<OrderItemResponse> {
    const newItem = await createOrderItem(orderId, payload)
    await refreshOrder(orderId)
    return newItem
  }

  async function deliverItem(
    orderId: number,
    orderItemId: number,
    quantity?: number,
    storagePlace?: string,
    rejection?: DeliveryRejectionRequest,
  ): Promise<void> {
    const before = statusOf(orderId)
    await deliverOrderItem(orderItemId, quantity, storagePlace, rejection)
    const after = await refreshOrder(orderId)
    celebrateIfDelivered(before, after)
  }

  /** Returns how many lines the backend skipped, as not deliverable. */
  async function deliverAllItems(
    orderId: number,
    storagePlace?: string,
    rejections?: OrderItemRejectionRequest[],
    deliveryNoteNumber?: string,
    damageNoted?: boolean,
  ): Promise<number> {
    const before = statusOf(orderId)
    const result = await deliverAllOrderItems(
      orderId,
      storagePlace,
      rejections,
      deliveryNoteNumber,
      damageNoted,
    )
    const after = await refreshOrder(orderId)
    celebrateIfDelivered(before, after)
    // Delivered and canceled lines are expected to be left out.
    const unexpected = result.skipped.filter(
      (line) => line.reason !== 'delivered' && line.reason !== 'canceled',
    )
    return unexpected.length
  }

  function statusOf(id: number): OrderStatus | undefined {
    return items.value.find((o) => o.id === id)?.status
  }

  /**
   * Confetti the moment an order becomes fully delivered, only on the
   * transition, so re-delivering against an already delivered order stays quiet.
   */
  function celebrateIfDelivered(before: OrderStatus | undefined, after: OrderResponse): void {
    if (after.status === 'delivered' && before !== 'delivered') {
      void celebrate()
    }
  }

  async function markItemOrdered(orderId: number, orderItemId: number): Promise<void> {
    await markOrderItemOrdered(orderId, orderItemId)
    await refreshOrder(orderId)
  }

  async function markAllItemsOrdered(orderId: number): Promise<void> {
    await markAllOrderItemsOrdered(orderId)
    await refreshOrder(orderId)
  }

  async function markItemRequested(orderId: number, orderItemId: number): Promise<void> {
    await markOrderItemRequested(orderId, orderItemId)
    await refreshOrder(orderId)
  }

  async function markAllItemsRequested(orderId: number): Promise<void> {
    await markAllOrderItemsRequested(orderId)
    await refreshOrder(orderId)
  }

  async function markItemReadyForPickup(orderId: number, orderItemId: number): Promise<void> {
    await markOrderItemReadyForPickup(orderId, orderItemId)
    await refreshOrder(orderId)
  }

  async function updateItem(
    orderId: number,
    itemId: number,
    payload: OrderItemUpdateRequest,
  ): Promise<void> {
    await updateOrderItem(orderId, itemId, payload)
    await refreshOrder(orderId)
  }

  async function removeItem(
    orderId: number,
    orderItemId: number,
    editVersion: number,
  ): Promise<void> {
    await removeOrderItem(orderId, orderItemId, editVersion)
    await refreshOrder(orderId)
  }

  async function cancelItem(
    orderId: number,
    orderItemId: number,
    editVersion: number,
  ): Promise<void> {
    await cancelOrderItem(orderId, orderItemId, editVersion)
    await refreshOrder(orderId)
  }

  async function closeItemShort(
    orderId: number,
    orderItemId: number,
    editVersion: number,
  ): Promise<void> {
    const before = statusOf(orderId)
    await closeOrderItemShort(orderId, orderItemId, editVersion)
    const after = await refreshOrder(orderId)
    celebrateIfDelivered(before, after)
  }

  async function reopenItem(
    orderId: number,
    orderItemId: number,
    editVersion: number,
  ): Promise<void> {
    await reopenOrderItem(orderId, orderItemId, editVersion)
    await refreshOrder(orderId)
  }

  async function correctDelivery(
    orderId: number,
    orderItemId: number,
    deliveryId: number,
    payload: CorrectDeliveryRequest,
  ): Promise<OrderItemResponse> {
    const corrected = await correctOrderItemDelivery(orderId, orderItemId, deliveryId, payload)
    await refreshOrder(orderId)
    return corrected
  }

  async function moveItem(item: OrderItemResponse, targetOrder: OrderResponse): Promise<void> {
    await moveOrderItem(item.order_id, item.id, targetOrder.id)
    await refreshOrder(item.order_id)
    await refreshOrder(targetOrder.id)
  }

  async function refreshOrder(id: number): Promise<OrderResponse> {
    const updated = await getOrder(id)
    const index = items.value.findIndex((o) => o.id === id)
    if (index !== -1) {
      items.value[index] = updated
    }
    return updated
  }

  function replaceItem(updated: OrderResponse): void {
    const index = items.value.findIndex((item) => item.id === updated.id)
    if (index !== -1) {
      items.value[index] = updated
    }
  }

  return {
    loading,
    error,
    items,
    total,
    refreshTrigger,
    refresh,
    triggerRefresh,
    clear,
    create,
    update,
    setExtraCosts,
    submit,
    request,
    cancel,
    refreshOrder,
    addItem,
    deliverItem,
    deliverAllItems,
    markItemOrdered,
    markAllItemsOrdered,
    markItemRequested,
    markAllItemsRequested,
    markItemReadyForPickup,
    updateItem,
    removeItem,
    cancelItem,
    closeItemShort,
    reopenItem,
    correctDelivery,
    moveItem,
    replaceItem,
  }
})
