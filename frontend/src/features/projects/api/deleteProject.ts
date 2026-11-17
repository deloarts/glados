import { webApi } from '@/core/api/webRequest'

/** Deletes a project; one changed since `expectedEditVersion` was read answers 409. */
export async function deleteProject(projectId: number, expectedEditVersion: number): Promise<void> {
  await webApi.delete('/projects/{project_id}', {
    path: { project_id: projectId },
    query: { expected_edit_version: expectedEditVersion },
  })
}
