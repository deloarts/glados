import { webApi } from '@/core/api/webRequest'
import type { ListPlaceTarget } from '@/shared/types/listOrder'

/** Puts the pool next to another one, as dragging its row does. */
export async function placeMachinePool(poolId: number, target: ListPlaceTarget): Promise<void> {
  await webApi.post('/production-machine-pools/{pool_id}/place', {
    path: { pool_id: poolId },
    body: target,
  })
}
