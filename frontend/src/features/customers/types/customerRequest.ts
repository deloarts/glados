import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type CustomerFilterParams = QueryOf<'/customers'>
export type CustomerSortBy = NonNullable<CustomerFilterParams['order_by']>
export type CustomerSortDir = NonNullable<CustomerFilterParams['order_dir']>

export type CustomerCreateRequest = Schemas['CustomerCreateRequest']

export type CustomerUpdateRequest = Schemas['CustomerUpdateRequest']
