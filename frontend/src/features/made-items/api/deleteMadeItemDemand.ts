import { webApi } from '@/core/api/webRequest'

import type { MadeItemDemandResponse } from '../types/madeItemsDemandsResponse'

export async function deleteMadeItemDemand(id: number): Promise<MadeItemDemandResponse> {
  return (await webApi.delete('/made-items-demands/{demand_id}', {
    path: { demand_id: id },
  })) as MadeItemDemandResponse
}
