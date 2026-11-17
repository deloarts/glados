import { webApi } from '@/core/api/webRequest'
import type { PdmPollResult } from '../types/adminSettingsTypes'

/**
 * Queues an immediate PDM poll (ControlsBar's "Synchronize with PDM"):
 * clears the stored `last_poll_at` so the scheduler's next tick, within 60
 * seconds, treats the vault as due rather than waiting out
 * `poll_interval_minutes`. 202 means queued, not done. Rejects with 409
 * when PDM is not enabled and configured.
 */
export async function requestPdmPoll(): Promise<PdmPollResult> {
  return webApi.post('/admin/settings/pdm/poll')
}
