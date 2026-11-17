import { webApi } from '@/core/api/webRequest'
import type { ChecklistResponse } from '../types/checklist'

export async function getChecklist(id: number): Promise<ChecklistResponse> {
  const checklist = await webApi.get('/checklists/{checklist_id}', { path: { checklist_id: id } })
  return { ...checklist, changes: checklist.changes ?? [] }
}
