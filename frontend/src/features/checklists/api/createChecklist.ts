import { webApi } from '@/core/api/webRequest'
import type { ChecklistCreateRequest, ChecklistResponse } from '../types/checklist'

export async function createChecklist(body: ChecklistCreateRequest): Promise<ChecklistResponse> {
  const checklist = await webApi.post('/checklists', { body })
  return { ...checklist, changes: checklist.changes ?? [] }
}
