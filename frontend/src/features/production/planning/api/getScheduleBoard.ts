import { webApi, type QueryOf } from '@/core/api/webRequest'

import type { ScheduleBoardResponse } from '../../types/scheduleBoardResponse'

export async function getScheduleBoard(
  params: QueryOf<'/production-schedule/'>,
): Promise<ScheduleBoardResponse> {
  return webApi.get('/production-schedule/', { query: params })
}
