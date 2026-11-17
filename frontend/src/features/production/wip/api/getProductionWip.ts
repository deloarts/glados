import { webApi } from '@/core/api/webRequest'

import type { WipLotResponse } from '../types/productionWipResponse'

export async function getProductionWip(): Promise<WipLotResponse[]> {
  return webApi.get('/production-wip/')
}
