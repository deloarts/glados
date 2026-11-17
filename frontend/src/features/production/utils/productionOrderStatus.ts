import type {
  ManufacturingComplexity,
  ProductionOrderPriority,
  ProductionOrderStatus,
} from '../types/productionOrdersResponse'

export const productionOrderStatusSeverity: Record<ProductionOrderStatus, string> = {
  queued: 'secondary',
  in_progress: 'warn',
  paused: 'help',
  completed: 'success',
  canceled: 'danger',
}

export const productionOrderPrioritySeverity: Record<ProductionOrderPriority, string> = {
  low: 'secondary',
  normal: 'info',
  high: 'warn',
  critical: 'danger',
}

export const MANUFACTURING_COMPLEXITIES: ManufacturingComplexity[] = ['low', 'normal', 'very']

/**
 * Mirrors the backend's ReorderProductionOrders use case rule: pinned or
 * IN_PROGRESS orders are never reorderable and must be excluded from the
 * `ordered_production_order_ids` payload entirely (the backend rejects the
 * whole request otherwise).
 */
export function isProductionOrderLocked(order: {
  pinned: boolean
  status: ProductionOrderStatus
}): boolean {
  return order.pinned || order.status === 'in_progress'
}

/** The statuses of work still ahead of the shop floor. */
export const OPEN_PRODUCTION_ORDER_STATUSES: ProductionOrderStatus[] = ['queued', 'in_progress', 'paused']

/** The statuses of finished work, completed or canceled. */
export const FINISHED_PRODUCTION_ORDER_STATUSES: ProductionOrderStatus[] = ['completed', 'canceled']

/**
 * How long finished work stays on the queue board after its last change.
 * The queue store loads finished orders only inside this window, and the
 * board shows the same ones.
 */
// Spelled out rather than built from DAY_MS: scripts/check-i18n-parity.ts
// loads this file without the `@/` alias.
export const FINISHED_ORDER_WINDOW_MS = 7 * 24 * 60 * 60 * 1000
