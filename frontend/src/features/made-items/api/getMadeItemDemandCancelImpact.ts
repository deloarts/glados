import { webApi } from '@/core/api/webRequest'

import type { MadeItemDemandCancelImpact } from '../types/madeItemsDemandsResponse'

export async function getMadeItemDemandCancelImpact(
  id: number,
): Promise<MadeItemDemandCancelImpact> {
  return webApi.get('/made-items-demands/{demand_id}/cancel-impact', { path: { demand_id: id } })
}
