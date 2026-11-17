import { webApi } from '@/core/api/webRequest'
import type { RestoreFilesResult } from '../types/adminSettingsTypes'

export async function restoreFiles(snapshotKey: string): Promise<RestoreFilesResult> {
  return webApi.post('/admin/settings/storage/backups/files/restore', {
    body: {
      snapshot_key: snapshotKey,
    },
  })
}
