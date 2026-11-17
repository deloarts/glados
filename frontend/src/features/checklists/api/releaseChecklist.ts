import { webApi } from '@/core/api/webRequest'
import type { ChecklistResponse } from '../types/checklist'

export async function releaseChecklist(id: number): Promise<ChecklistResponse> {
  const checklist = await webApi.post('/checklists/{checklist_id}/release', {
    path: { checklist_id: id },
  })
  return { ...checklist, changes: checklist.changes ?? [] }
}
