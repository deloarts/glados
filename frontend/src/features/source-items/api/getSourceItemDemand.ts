import { webApi } from '@/core/api/webRequest'

import type { SourceItemDemandResponse } from '../types/sourceItemDemandsResponse'

export async function getSourceItemDemand(demandId: number): Promise<SourceItemDemandResponse> {
  return webApi.get('/source-item-demands/{demand_id}', {
    path: { demand_id: demandId },
  })
}
