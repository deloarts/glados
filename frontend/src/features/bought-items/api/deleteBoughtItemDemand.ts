import { webApi } from '@/core/api/webRequest'

import type { BoughtItemDemandResponse } from '../types/boughtItemsDemandsResponse'

export async function deleteBoughtItemDemand(id: number): Promise<BoughtItemDemandResponse> {
  return (await webApi.delete('/bought-items-demands/{demand_id}', {
    path: { demand_id: id },
  })) as BoughtItemDemandResponse
}
