import { webApi } from '@/core/api/webRequest'
import type { IntegrationsOverview } from '../types/adminSettingsTypes'

/**
 * Which integrations are switched on and configured, read from the stored
 * settings. Loaded once when the Host tab opens, unlike the polled services
 * panel, since it only changes when a setting is saved.
 */
export async function getIntegrationsOverview(): Promise<IntegrationsOverview> {
  return webApi.get('/admin/settings/host/integrations')
}
