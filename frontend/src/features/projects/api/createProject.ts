import { webApi } from '@/core/api/webRequest'

import type { ProjectCreateRequest } from '../types/projectRequest'
import type { ProjectResponse } from '../types/projectResponse'

export async function createProject(payload: ProjectCreateRequest): Promise<ProjectResponse> {
  return webApi.post('/projects/', { body: payload })
}
