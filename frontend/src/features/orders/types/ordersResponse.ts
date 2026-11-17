import type { Schemas } from '@/core/api/generated'

export type OrderFileCategory = Schemas['OrderFileCategory']

export type OrderFile = Schemas['OrderFileResponse']

export type OrderStatus = Schemas['OrderStatus']
export type OrderItemStatus = Schemas['OrderItemStatus']
export type DeliverAllResponse = Schemas['DeliverAllResponse']

export type ExtraCostKind = Schemas['ExtraCostKind']
export type OrderExtraCost = Schemas['OrderExtraCostResponse']

export type DemandSubstitutionInfo = Schemas['DemandSubstitutionInfo']

/** Only delivery_date is emitted for a delivery record. */
export type DeliveryRecord = Schemas['DeliveryRecordInfo']

export type OrderItemLineType = Schemas['OrderLineType']

/**
 * Outcome of a rejected quantity: the supplier re-delivers, or the pieces
 * are lost.
 */
export type RejectionOutcome = Schemas['RejectionOutcome']

// Optional although the schema marks them required; callers read them with
// a fallback.
export type OrderItemResponse = Omit<
  Schemas['OrderItemResponse'],
  'quantity_rejected' | 'quantity_rejected_lost'
> & {
  quantity_rejected?: number
  quantity_rejected_lost?: number
}

// items uses the aliased OrderItemResponse.
export type OrderResponse = Omit<Schemas['OrderResponse'], 'items'> & {
  items: OrderItemResponse[]
}
