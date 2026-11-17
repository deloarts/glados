import type { PageResponse } from '@/core/api/types'
import type { AdminSettingsAuditEntry } from '../types/adminSettingsTypes'
import { webApi, type QueryOf } from '@/core/api/webRequest'

export type SettingsAuditParams = QueryOf<'/admin/settings/audit'>

export async function getSettingsAudit(
  params?: SettingsAuditParams,
): Promise<PageResponse<AdminSettingsAuditEntry>> {
  return webApi.get('/admin/settings/audit', { query: params })
}
