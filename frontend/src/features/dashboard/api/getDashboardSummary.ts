import { webApi } from '@/core/api/webRequest'

import type { DashboardSummaryResponse } from '../types/dashboardSummaryResponse'

export async function getDashboardSummary(): Promise<DashboardSummaryResponse> {
  return webApi.get('/dashboard/summary')
}
