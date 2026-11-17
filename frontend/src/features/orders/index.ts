// Public barrel of the orders feature. Other features import through here
// (enforced by eslint). Export only what other features consume.

export { createOrderItem } from './api/createOrderItem'
export { getOrder } from './api/getOrder'
export { getOrders } from './api/getOrders'
export { getOrdersByIds } from './api/getOrdersByIds'
export { updateOrderItem } from './api/updateOrderItem'
export { useOrderFormatters } from './composables/useOrderFormatters'
export { getDefaultMailTemplate } from './api/getDefaultMailTemplate'
export { OPEN_ORDER_STATUSES } from './utils/openOrderStatuses'

export type { OrderItemResponse, OrderResponse } from './types/ordersResponse'
export type { OrderItemCreateRequest } from './types/ordersRequest'

export { default as OrderCreateForm } from './components/OrderCreateForm.vue'
export { default as OrderDetailDialog } from './components/OrderDetailDialog.vue'
export { default as OrderItemCreateForm } from './components/OrderItemCreateForm.vue'
export { default as OrderSelect } from './components/OrderSelect.vue'

// The order dialogs the bought-item catalogue opens from a row, provided by
// the page that hosts the catalogue.
export { default as BoughtItemAddToOrderDialog } from './components/BoughtItemAddToOrderDialog.vue'
export { default as BoughtItemOrderHistoryDialog } from './components/BoughtItemOrderHistoryDialog.vue'
