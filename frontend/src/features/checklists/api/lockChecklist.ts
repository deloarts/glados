import { webApi } from '@/core/api/webRequest'
import type { ChecklistResponse } from '../types/checklist'

/** Takes the edit lock, or renews the one the caller holds; `takeOver` takes it from another editor. */
export async function lockChecklist(id: number, takeOver = false): Promise<ChecklistResponse> {
  const checklist = await webApi.post('/checklists/{checklist_id}/lock', {
    path: { checklist_id: id },
    body: { take_over: takeOver },
  })
  return { ...checklist, changes: checklist.changes ?? [] }
}

/** Ends the edit lock the caller holds; `force` ends anyone's, which needs the manage permission. */
export async function unlockChecklist(id: number, force = false): Promise<ChecklistResponse> {
  const checklist = await webApi.delete('/checklists/{checklist_id}/lock', { path: { checklist_id: id }, query: { force } })
  return { ...checklist, changes: checklist.changes ?? [] }
}
