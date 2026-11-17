import { webApi } from '@/core/api/webRequest'

import type { ProjectSummaryResponse } from '../types/projectResponse'

export async function getProjectSummary(projectId: number): Promise<ProjectSummaryResponse> {
  return webApi.get('/projects/{project_id}/summary', { path: { project_id: projectId } })
}
