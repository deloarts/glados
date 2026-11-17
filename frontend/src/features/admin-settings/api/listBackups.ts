import { webApi } from '@/core/api/webRequest'
import type { BackupList } from '../types/adminSettingsTypes'

export async function listBackups(): Promise<BackupList> {
  return webApi.get('/admin/settings/storage/backups')
}
