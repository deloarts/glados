import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type ProductFamilyFilterParams = QueryOf<'/product-families'>
export type ProductFamilySortBy = NonNullable<ProductFamilyFilterParams['order_by']>
export type ProductFamilySortDir = NonNullable<ProductFamilyFilterParams['order_dir']>

// These fields default on the backend when omitted.
type ProductFamilyDefaultedFields = 'description' | 'label_color' | 'label_font_color'

export type ProductFamilyCreateRequest = Omit<
  Schemas['ProductFamilyCreateRequest'],
  ProductFamilyDefaultedFields
> & {
  description?: string | null
  label_color?: string | null
  label_font_color?: string | null
}

export type ProductFamilyUpdateRequest = Omit<
  Schemas['ProductFamilyUpdateRequest'],
  ProductFamilyDefaultedFields
> & {
  description?: string | null
  label_color?: string | null
  label_font_color?: string | null
}
