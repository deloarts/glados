import { webApi } from '@/core/api/webRequest'
import type { ChecklistResponse } from '../types/checklist'

/** Marks a released revision invalid; it stays released and on record. */
export async function markChecklistInvalid(id: number, reason: string): Promise<ChecklistResponse> {
  const checklist = await webApi.post('/checklists/{checklist_id}/mark-invalid', {
    path: { checklist_id: id },
    body: { reason },
  })
  return { ...checklist, changes: checklist.changes ?? [] }
}
