import type { PageResponse } from '@/core/api/types'
import type { SecurityEvent } from '../types/adminSettingsTypes'
import { webApi, type QueryOf } from '@/core/api/webRequest'

export type SecurityEventsParams = QueryOf<'/admin/settings/security-events'>

export async function getSecurityEvents(
  params?: SecurityEventsParams,
): Promise<PageResponse<SecurityEvent>> {
  return webApi.get('/admin/settings/security-events', { query: params })
}
