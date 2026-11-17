import { webApi } from '@/core/api/webRequest'

import type { AutoPlanRunStatus } from '../types/scheduleBoardResponse'

// Source of truth for every client that isn't the one running it. Late
// joiners, page reloads, and reconnects all recover through this rather
// than depending on having received a live signal.
export async function getAutoPlanRunStatus(): Promise<AutoPlanRunStatus> {
  return webApi.get('/production-schedule/auto-plan/status')
}
