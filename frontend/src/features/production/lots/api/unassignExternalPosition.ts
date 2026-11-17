import { webApi } from '@/core/api/webRequest'

export async function unassignExternalPosition(lotId: number, positionId: number): Promise<void> {
  await webApi.delete('/production-lots/{lot_id}/positions/{position_id}/assign', {
    path: { lot_id: lotId, position_id: positionId },
  })
}
