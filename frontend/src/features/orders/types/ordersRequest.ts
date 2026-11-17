import type { OrderStatus } from './ordersResponse'
import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type { OrderStatus }

/**
 * Optional rejection booking alongside a single-item delivery call. The
 * damage-noted flag defaults to false on the backend, so a caller leaves it
 * out unless it was ticked.
 */
export type DeliveryRejectionRequest = Omit<
  Schemas['DeliveryRejectionRequest'],
  'damage_noted_on_delivery_note'
> &
  Partial<Pick<Schemas['DeliveryRejectionRequest'], 'damage_noted_on_delivery_note'>>

/** One line's rejection within a deliver-all-items call. */
export type OrderItemRejectionRequest = Schemas['OrderItemRejectionRequest']

export type OrderCreateRequest = Schemas['OrderCreateRequest']

// update_items_delivery_date defaults to false on the backend.
export type OrderUpdateRequest = Omit<
  Schemas['OrderUpdateRequest'],
  'update_items_delivery_date'
> & {
  update_items_delivery_date?: boolean
}

export type OrderExtraCostRequest = Schemas['OrderExtraCostRequest']
export type OrderExtraCostsUpdateRequest = Schemas['OrderExtraCostsUpdateRequest']

export type OrderItemCreateRequest = Schemas['OrderItemCreateRequest']

export type OrderItemUpdateRequest = Schemas['OrderItemUpdateRequest']

/** Accepted pieces of one delivery taken back, with the reason. */
export type CorrectDeliveryRequest = Schemas['CorrectDeliveryRequest']

export type OrderFilterParams = QueryOf<'/orders'>
export type OrderSortBy = NonNullable<OrderFilterParams['order_by']>
export type OrderSortDir = NonNullable<OrderFilterParams['order_dir']>
