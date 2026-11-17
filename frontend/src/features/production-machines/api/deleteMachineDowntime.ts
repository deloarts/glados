import { webApi } from '@/core/api/webRequest'

export async function deleteMachineDowntime(downtimeId: number): Promise<void> {
  await webApi.delete('/production-machines/downtimes/{downtime_id}', {
    path: { downtime_id: downtimeId },
  })
}
