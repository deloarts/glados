import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'

/** The host's feature switches. time_tracking_provider_label is null while time tracking is off. */
export type HostFeatureFlags = Schemas['FeatureFlags']

/**
 * What every signed-in user's UI needs to know about the host. Feature flags
 * live here, not under /admin/settings, because reading the admin settings
 * requires read:settings. The locale defaults are tenant-wide and also needed
 * before sign-in.
 */
export type HostCapabilities = Schemas['ServerCapabilities']

export async function getCapabilities(): Promise<HostCapabilities> {
  return webApi.get('/host/capabilities')
}
