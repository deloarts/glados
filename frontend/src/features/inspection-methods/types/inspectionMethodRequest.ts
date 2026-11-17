import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'
import type { LocalizedText } from '@/shared/utils/localizedText'

export type InspectionMethodFilterParams = QueryOf<'/inspection-methods'>
export type InspectionMethodSortBy = NonNullable<InspectionMethodFilterParams['order_by']>
export type InspectionMethodSortDir = NonNullable<InspectionMethodFilterParams['order_dir']>

// These fields default on the backend when omitted.
type InspectionMethodDefaultedFields =
  | 'description'
  | 'label_color'
  | 'label_font_color'
  | 'requires_evidence'

export type InspectionMethodCreateRequest = Omit<
  Schemas['InspectionMethodCreateRequest'],
  InspectionMethodDefaultedFields
> & {
  description?: LocalizedText | null
  label_color?: string | null
  label_font_color?: string | null
  requires_evidence?: boolean | null
}

export type InspectionMethodUpdateRequest = Omit<
  Schemas['InspectionMethodUpdateRequest'],
  InspectionMethodDefaultedFields
> & {
  description?: LocalizedText | null
  label_color?: string | null
  label_font_color?: string | null
  requires_evidence?: boolean | null
}
