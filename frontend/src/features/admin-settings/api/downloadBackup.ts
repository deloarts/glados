import { webApi } from '@/core/api/webRequest'
import { downloadBlob } from '@/core/utils/downloadBlob'

/**
 * Downloads a single DB archive's raw bytes and saves it under its own
 * filename. Gated by `write:settings`, same as everywhere else a full backup
 * key is handed to the server (see `download_backup` in the backend's
 * `admin_settings/backup.py`).
 */
export async function downloadBackup(key: string): Promise<void> {
  // The schema declares no body type for a file download, so the blob is cast.
  const blob = await webApi.get('/admin/settings/storage/backups/download', {
    query: { key },
    config: { responseType: 'blob' },
  })
  downloadBlob(blob as Blob, key.split('/').pop() ?? key)
}
