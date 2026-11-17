import { webApi } from '@/core/api/webRequest'
import type { HostStats } from '../types/adminSettingsTypes'

/**
 * Live machine reading. Polled by the Host tab, so kept out of the aggregate
 * settings fetch, a snapshot is only meaningful at the moment it is taken.
 */
export async function getHostStats(): Promise<HostStats> {
  return webApi.get('/admin/settings/host/stats')
}
