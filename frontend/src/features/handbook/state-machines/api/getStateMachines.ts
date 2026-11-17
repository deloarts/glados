import { webApi } from '@/core/api/webRequest'

import type { StateMachinesResponse } from '../types/stateMachinesResponse'

// Computed live on the backend on every request; the store caches it per
// session. The trailing slash avoids a 307 redirect.
export async function getStateMachines(): Promise<StateMachinesResponse> {
  return webApi.get('/state-machines/')
}
