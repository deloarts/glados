import { webApi } from '@/core/api/webRequest'
import type { PdmFileRetryResult } from '../types/adminSettingsTypes'

/**
 * The same retry as retryPdmFile, addressed by the vault file id a
 * reconciliation finding carries. 202 means queued, not done.
 */
export async function retryPdmVaultFile(fileId: number): Promise<PdmFileRetryResult> {
  return webApi.post('/admin/settings/pdm/vault-files/{file_id}/retry', {
    path: { file_id: fileId },
  })
}
