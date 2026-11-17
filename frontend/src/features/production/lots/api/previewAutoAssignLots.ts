import { webApi } from '@/core/api/webRequest'

import type { AutoAssignLotGroupResponse } from '../../types/productionLotsResponse'

export async function previewAutoAssignLots(): Promise<AutoAssignLotGroupResponse[]> {
  return webApi.post('/production-lots/auto-assign/preview')
}
