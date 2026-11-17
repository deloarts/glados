import { webApi } from '@/core/api/webRequest'

import type { PlanningExceptionResponse } from '../types/planningExceptionResponse'

export async function getPlanningExceptions(): Promise<PlanningExceptionResponse[]> {
  return webApi.get('/production-exceptions/')
}
