import { webApi } from '@/core/api/webRequest'

export async function deleteMadeItemProcess(itemId: number, processId: number): Promise<void> {
  await webApi.delete('/made-items/{item_id}/processes/{process_id}', {
    path: { item_id: itemId, process_id: processId },
  })
}
