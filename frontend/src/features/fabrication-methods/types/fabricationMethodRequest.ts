import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'
import type { LocalizedText } from '@/shared/utils/localizedText'

export type FabricationMethodFilterParams = QueryOf<'/fabrication-methods'>
export type FabricationMethodSortBy = NonNullable<FabricationMethodFilterParams['order_by']>
export type FabricationMethodSortDir = NonNullable<FabricationMethodFilterParams['order_dir']>

// These fields default on the backend when omitted.
type FabricationMethodDefaultedFields =
  | 'description'
  | 'label_color'
  | 'label_font_color'
  | 'requires_machine'
  | 'required_external'
  | 'default_for_assemblies'

export type FabricationMethodCreateRequest = Omit<
  Schemas['FabricationMethodCreateRequest'],
  FabricationMethodDefaultedFields
> & {
  description?: LocalizedText | null
  label_color?: string | null
  label_font_color?: string | null
  requires_machine?: boolean | null
  required_external?: boolean | null
  default_for_assemblies?: boolean | null
}

export type FabricationMethodUpdateRequest = Omit<
  Schemas['FabricationMethodUpdateRequest'],
  FabricationMethodDefaultedFields
> & {
  description?: LocalizedText | null
  label_color?: string | null
  label_font_color?: string | null
  requires_machine?: boolean | null
  required_external?: boolean | null
  default_for_assemblies?: boolean | null
}
