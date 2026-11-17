import { webApi } from '@/core/api/webRequest'
import type { AdminDataImportSettings } from '../types/adminSettingsTypes'

export async function getDataImportSettings(): Promise<AdminDataImportSettings> {
  return webApi.get('/admin/settings/data-import')
}
