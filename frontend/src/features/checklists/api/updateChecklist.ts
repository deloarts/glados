import { webApi } from '@/core/api/webRequest'
import type { ChecklistResponse, ChecklistUpdateRequest } from '../types/checklist'

export async function updateChecklist(
  id: number,
  body: ChecklistUpdateRequest,
): Promise<ChecklistResponse> {
  const checklist = await webApi.put('/checklists/{checklist_id}', {
    path: { checklist_id: id },
    body,
  })
  return { ...checklist, changes: checklist.changes ?? [] }
}
