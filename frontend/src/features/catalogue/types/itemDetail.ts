import type { DemandStatusValue } from '@/core/utils/demandStatus'
import type { OrderItemResponse, OrderResponse } from '@/features/orders'
import type { PublicUser } from '@/core/types/userResponse'

/** The three catalogue item kinds an item-detail page can be built for. */
export type CatalogueItemKind = 'bought' | 'made' | 'source'

/**
 * One demand row with the fields every kind shares. extra carries the
 * kind-specific value (made's alteration marker, source's lot number).
 */
export interface ItemDemandRow {
  id: number
  status: DemandStatusValue
  quantity: number
  unit: string
  highPriority: boolean
  projectNumber: string
  projectCustomer: string | null
  desiredDeliveryDate: string | null
  created: string
  creatorName: string
  /** The creator whose card opens from the name below the created date. */
  creator?: PublicUser | null
  extra?: string
}

/** One order item of this catalogue item with its parent order. */
export interface ItemOrderRow {
  order: OrderResponse
  orderItem: OrderItemResponse
}

/**
 * The demand fields the usage aggregation reads, plus the project's
 * denormalized fields.
 */
export interface ItemUsageDemand {
  projectId: number
  projectNumber: string
  projectCustomer: string | null
  projectDescription: string | null
  projectStatus: string | null
  quantity: number
  status: DemandStatusValue
}

/** One project this item is used in. */
export interface ItemUsageRow {
  projectId: number
  projectNumber: string
  projectCustomer: string | null
  projectDescription: string | null
  projectStatus: string | null
  productNumber: string | null
  productDescription: string | null
  qtyDemanded: number
  qtyFulfilled: number
  demandCount: number
  fulfilledOrders: { orderId: number; orderNumber: string }[]
}

/**
 * Per-card load state of one detail page section, built with createSection
 * and runSection.
 */
export interface SectionState<T> {
  data: T
  loading: boolean
  error: boolean
  truncated: boolean
}
