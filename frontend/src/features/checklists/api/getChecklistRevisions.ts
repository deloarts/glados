import { webApi } from '@/core/api/webRequest'
import type { ChecklistSummaryResponse } from '../types/checklist'

/** Every revision of the checklist's lineage, newest first. */
export async function getChecklistRevisions(id: number): Promise<ChecklistSummaryResponse[]> {
  return webApi.get('/checklists/{checklist_id}/revisions', { path: { checklist_id: id } })
}
