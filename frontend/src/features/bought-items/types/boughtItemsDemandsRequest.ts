import type { BoughtItemDemandStatus } from './boughtItemsDemandsResponse'
import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type { BoughtItemDemandStatus }

// These fields default on the backend when omitted.
type DemandItemDefaultedFields = 'high_priority' | 'items_per_unit' | 'notify_on_delivery'

export type DemandItemCreateRequest = Omit<
  Schemas['DemandItemCreateRequest'],
  DemandItemDefaultedFields
> & {
  high_priority?: boolean
  items_per_unit?: number
  notify_on_delivery?: boolean
}

export type DemandItemUpdateRequest = Omit<
  Schemas['DemandItemUpdateRequest'],
  DemandItemDefaultedFields
> & {
  high_priority?: boolean
  items_per_unit?: number
  notify_on_delivery?: boolean
}

export type DemandItemFilterParams = QueryOf<'/bought-items-demands'>
export type DemandItemSortBy = NonNullable<DemandItemFilterParams['order_by']>
export type DemandItemSortDir = NonNullable<DemandItemFilterParams['order_dir']>
