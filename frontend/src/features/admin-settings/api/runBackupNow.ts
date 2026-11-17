import { webApi } from '@/core/api/webRequest'

export async function runBackupNow(): Promise<void> {
  await webApi.post('/admin/settings/storage/backups/run-now')
}
