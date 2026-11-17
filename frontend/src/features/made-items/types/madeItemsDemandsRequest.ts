import type { MadeItemDemandStatus } from './madeItemsDemandsResponse'
import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type { MadeItemDemandStatus }

// These fields default on the backend when omitted.
type MadeItemDemandDefaultedFields =
  | 'high_priority'
  | 'is_alteration'
  | 'items_per_unit'
  | 'notify_on_delivery'

export type MadeItemDemandCreateRequest = Omit<
  Schemas['MadeItemDemandCreateRequest'],
  MadeItemDemandDefaultedFields
> & {
  high_priority?: boolean
  is_alteration?: boolean
  items_per_unit?: number
  notify_on_delivery?: boolean
}

export type MadeItemDemandUpdateRequest = Omit<
  Schemas['MadeItemDemandUpdateRequest'],
  MadeItemDemandDefaultedFields
> & {
  high_priority?: boolean
  is_alteration?: boolean
  items_per_unit?: number
  notify_on_delivery?: boolean
}

export type MadeItemDemandFilterParams = QueryOf<'/made-items-demands'>
export type MadeItemDemandSortBy = NonNullable<MadeItemDemandFilterParams['order_by']>
export type MadeItemDemandSortDir = NonNullable<MadeItemDemandFilterParams['order_dir']>
