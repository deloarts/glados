import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type ProductFilterParams = QueryOf<'/products'>
export type ProductSortBy = NonNullable<ProductFilterParams['order_by']>
export type ProductSortDir = NonNullable<ProductFilterParams['order_dir']>

export type ProductCreateRequest = Schemas['ProductCreateRequest']

export type ProductUpdateRequest = Schemas['ProductUpdateRequest']
