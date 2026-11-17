import { webApi } from '@/core/api/webRequest'
import type { ServicesHealth } from '../types/adminSettingsTypes'

/**
 * Live connectivity check. Polled by the Host tab, so kept out of the
 * aggregate settings fetch, a reading is only meaningful at the moment
 * it is taken.
 */
export async function getServicesHealth(): Promise<ServicesHealth> {
  return webApi.get('/admin/settings/host/services')
}
