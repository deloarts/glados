import { webApi, type QueryOf } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { ProjectRef } from '@/core/types/projectRef'

export type ProjectSearchParams = Pick<
  QueryOf<'/projects'>,
  'limit' | 'status' | 'project_number' | 'ids' | 'order_by' | 'order_dir'
>

// Slim, cross-feature-safe project search used by the shared ProjectSelect
// picker and the demand tables' project filter. Kept separate from features/projects/api/getProjects, which
// returns the full ProjectResponse (with nested product/customer/creator)
// for the projects feature's own management screens.
export async function searchProjects(
  params?: ProjectSearchParams,
): Promise<PageResponse<ProjectRef>> {
  return webApi.get('/projects/', { query: params })
}
