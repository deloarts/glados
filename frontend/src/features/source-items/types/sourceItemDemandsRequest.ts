import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type SourceItemDemandFilterParams = QueryOf<'/source-item-demands'>
export type SourceItemDemandSortBy = NonNullable<SourceItemDemandFilterParams['order_by']>
export type SourceItemDemandSortDir = NonNullable<SourceItemDemandFilterParams['order_dir']>

// These fields default on the backend when omitted.
export type SourceItemDemandCreateRequest = Omit<
  Schemas['SourceItemDemandCreateRequest'],
  'high_priority' | 'items_per_unit' | 'notify_on_delivery' | 'unit'
> & {
  unit?: string
  high_priority?: boolean
  items_per_unit?: number
  notify_on_delivery?: boolean
}

export type SourceItemDemandUpdateRequest = Omit<
  Schemas['SourceItemDemandUpdateRequest'],
  'high_priority' | 'items_per_unit' | 'notify_on_delivery'
> & {
  high_priority?: boolean
  items_per_unit?: number
  notify_on_delivery?: boolean
}
