import { webApi } from '@/core/api/webRequest'

export async function deleteLotStep(lotId: number, stepId: number): Promise<void> {
  await webApi.delete('/production-lots/{lot_id}/steps/{step_id}', {
    path: { lot_id: lotId, step_id: stepId },
  })
}
