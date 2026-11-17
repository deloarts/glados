import { webApi } from '@/core/api/webRequest'
import type { ChecklistResponse } from '../types/checklist'

/** Starts the next revision of a finished checklist and returns it. */
export async function reviseChecklist(id: number, reason: string): Promise<ChecklistResponse> {
  const checklist = await webApi.post('/checklists/{checklist_id}/revise', {
    path: { checklist_id: id },
    body: { reason },
  })
  return { ...checklist, changes: checklist.changes ?? [] }
}
