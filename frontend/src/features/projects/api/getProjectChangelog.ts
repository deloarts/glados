import { getChangelog } from '@/shared/api/getChangelog'

import type { ProjectChangelogEntry } from '../types/projectChangelogResponse'

export async function getProjectChangelog(projectId: number): Promise<ProjectChangelogEntry[]> {
  return getChangelog('/projects/{project_id}/changelog', { path: { project_id: projectId } })
}
