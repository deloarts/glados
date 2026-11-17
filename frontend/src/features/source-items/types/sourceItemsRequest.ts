import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type SourceItemFilterParams = QueryOf<'/source-items'>
export type SourceItemSortBy = NonNullable<SourceItemFilterParams['order_by']>
export type SourceItemSortDir = NonNullable<SourceItemFilterParams['order_dir']>

export type SourceItemCreateRequest = Schemas['SourceItemWebCreateRequest']

export type SourceItemUpdateRequest = Schemas['SourceItemUpdateRequest']
