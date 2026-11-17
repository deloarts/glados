import { webApi } from '@/core/api/webRequest'

import type { ProjectUpdateRequest } from '../types/projectRequest'
import type { ProjectResponse } from '../types/projectResponse'

export async function updateProject(
  projectId: number,
  payload: ProjectUpdateRequest,
): Promise<ProjectResponse> {
  return webApi.put('/projects/{project_id}', { path: { project_id: projectId }, body: payload })
}
