import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { ProjectFilterParams } from '../types/projectRequest'
import type { ProjectResponse } from '../types/projectResponse'

export async function getProjects(
  params?: ProjectFilterParams,
): Promise<PageResponse<ProjectResponse>> {
  return webApi.get('/projects/', { query: params })
}
