import { webApi } from '@/core/api/webRequest'

export async function deleteChecklist(id: number): Promise<void> {
  await webApi.delete('/checklists/{checklist_id}', { path: { checklist_id: id } })
}
