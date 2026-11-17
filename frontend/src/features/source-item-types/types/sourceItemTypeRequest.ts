import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'
import type { LocalizedText } from '@/shared/utils/localizedText'

export type SourceItemTypeFilterParams = QueryOf<'/source-item-types'>
export type SourceItemTypeSortBy = NonNullable<SourceItemTypeFilterParams['order_by']>
export type SourceItemTypeSortDir = NonNullable<SourceItemTypeFilterParams['order_dir']>

// These fields default on the backend when omitted.
type SourceItemTypeDefaultedFields = 'description' | 'label_color' | 'label_font_color'

export type SourceItemTypeCreateRequest = Omit<
  Schemas['SourceItemTypeCreateRequest'],
  SourceItemTypeDefaultedFields
> & {
  description?: LocalizedText | null
  label_color?: string | null
  label_font_color?: string | null
}

export type SourceItemTypeUpdateRequest = Omit<
  Schemas['SourceItemTypeUpdateRequest'],
  SourceItemTypeDefaultedFields
> & {
  description?: LocalizedText | null
  label_color?: string | null
  label_font_color?: string | null
}
