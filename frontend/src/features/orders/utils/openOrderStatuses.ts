import type { OrderStatus } from '../types/ordersResponse'

export const OPEN_ORDER_STATUSES = [
  'draft',
  'requested',
  'partially_ordered',
  'ordered',
  'partially_delivered',
] as const satisfies readonly OrderStatus[]
