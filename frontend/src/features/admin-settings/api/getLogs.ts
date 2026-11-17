import { webApi } from '@/core/api/webRequest'
import type { LogEntriesResponse, LogFilterParams } from '../types/adminSettingsTypes'

export async function getLogs(params?: LogFilterParams): Promise<LogEntriesResponse> {
  return webApi.get('/logs/', { query: params })
}
