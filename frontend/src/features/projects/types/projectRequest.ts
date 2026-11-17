import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type ProjectFilterParams = QueryOf<'/projects'>
export type ProjectSortBy = NonNullable<ProjectFilterParams['order_by']>
export type ProjectSortDir = NonNullable<ProjectFilterParams['order_dir']>

export type ProjectCreateRequest = Schemas['ProjectCreateRequest']

export type ProjectUpdateRequest = Schemas['ProjectUpdateRequest']
