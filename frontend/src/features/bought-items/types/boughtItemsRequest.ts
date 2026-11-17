import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type BoughtItemFilterParams = QueryOf<'/bought-items'>
export type BoughtItemSortBy = NonNullable<BoughtItemFilterParams['order_by']>
export type BoughtItemSortDir = NonNullable<BoughtItemFilterParams['order_dir']>

export type BoughtItemDataSource = Schemas['DataSource']

// A new item cannot have a successor yet.
export type BoughtItemCreateRequest = Schemas['BoughtItemWebCreateRequest']

export type BoughtItemUpdateRequest = Schemas['BoughtItemWebUpdateRequest']
