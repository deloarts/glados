import { ref } from 'vue'

import type { OrderItemResponse, OrderResponse } from '../types/ordersResponse'

// The per-order/per-item dialogs OrdersTable opens directly: each is just a
// visibility flag plus the row or target it was opened for.
export function useOrdersTableDialogs() {
  const addItemOrderId = ref<number | null>(null)
  const addItemSupplierId = ref<number>(0)
  const showAddItem = ref(false)

  function openAddItem(order: OrderResponse): void {
    addItemOrderId.value = order.id
    addItemSupplierId.value = order.supplier_id
    showAddItem.value = true
  }

  const deliverTarget = ref<{ orderId: number; item: OrderItemResponse } | null>(null)
  const showDeliverDialog = ref(false)

  function openDeliverDialog(orderId: number, item: OrderItemResponse): void {
    deliverTarget.value = { orderId, item }
    showDeliverDialog.value = true
  }

  const historyTarget = ref<OrderItemResponse | null>(null)
  const showHistoryDialog = ref(false)

  function openHistoryDialog(item: OrderItemResponse): void {
    historyTarget.value = item
    showHistoryDialog.value = true
  }

  const deliverAllOrderId = ref<number | null>(null)
  const showDeliverAllDialog = ref(false)

  function openDeliverAllDialog(orderId: number): void {
    deliverAllOrderId.value = orderId
    showDeliverAllDialog.value = true
  }

  const moveTarget = ref<OrderItemResponse | null>(null)
  const showMoveItemDialog = ref(false)

  function openMoveItemDialog(item: OrderItemResponse): void {
    moveTarget.value = item
    showMoveItemDialog.value = true
  }

  return {
    addItemOrderId,
    addItemSupplierId,
    showAddItem,
    openAddItem,
    deliverTarget,
    showDeliverDialog,
    openDeliverDialog,
    historyTarget,
    showHistoryDialog,
    openHistoryDialog,
    deliverAllOrderId,
    showDeliverAllDialog,
    openDeliverAllDialog,
    moveTarget,
    showMoveItemDialog,
    openMoveItemDialog,
  }
}
