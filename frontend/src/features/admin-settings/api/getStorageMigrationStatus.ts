import { webApi } from '@/core/api/webRequest'
import type { StorageMigrationStatus } from '../types/adminSettingsTypes'

export async function getStorageMigrationStatus(): Promise<StorageMigrationStatus> {
  return webApi.get('/admin/settings/storage/migrate/status')
}
