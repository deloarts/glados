import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type SupplierFilterParams = QueryOf<'/suppliers'>
export type SupplierSortBy = NonNullable<SupplierFilterParams['order_by']>
export type SupplierSortDir = NonNullable<SupplierFilterParams['order_dir']>

// level defaults to 'B' on create; on update it is required.
export type SupplierCreateRequest = Omit<Schemas['SupplierCreateRequest'], 'level'> & {
  level?: Schemas['SupplierLevel']
}

export type SupplierUpdateRequest = Schemas['SupplierUpdateRequest']
