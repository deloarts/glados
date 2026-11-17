import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'
import type { LocalizedText } from '@/shared/utils/localizedText'

export type ArticleGroupFilterParams = QueryOf<'/article-groups'>
export type ArticleGroupSortBy = NonNullable<ArticleGroupFilterParams['order_by']>
export type ArticleGroupSortDir = NonNullable<ArticleGroupFilterParams['order_dir']>

// These fields default on the backend when omitted.
type ArticleGroupDefaultedFields = 'description' | 'label_color' | 'label_font_color'

export type ArticleGroupCreateRequest = Omit<
  Schemas['ArticleGroupCreateRequest'],
  ArticleGroupDefaultedFields
> & {
  description?: LocalizedText | null
  label_color?: string | null
  label_font_color?: string | null
}

export type ArticleGroupUpdateRequest = Omit<
  Schemas['ArticleGroupUpdateRequest'],
  ArticleGroupDefaultedFields
> & {
  description?: LocalizedText | null
  label_color?: string | null
  label_font_color?: string | null
}
