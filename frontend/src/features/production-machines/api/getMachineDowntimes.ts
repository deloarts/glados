import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type {
  MachineDowntimeFilterParams,
  MachineDowntimeResponse,
} from '../types/machineDowntimeResponse'

export async function getMachineDowntimes(
  params?: MachineDowntimeFilterParams,
): Promise<PageResponse<MachineDowntimeResponse>> {
  return webApi.get('/production-machines/downtimes', {
    query: params,
  })
}
