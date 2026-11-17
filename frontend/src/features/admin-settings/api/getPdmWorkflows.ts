import { webApi } from '@/core/api/webRequest'
import type { PdmWorkflow } from '../types/adminSettingsTypes'

/**
 * Proxies the SOLIDWORKS PDM vault's workflow list under the saved
 * connection and its shared session, for the SolidWorks PDM section's
 * "Released States"/"Obsolete States" pickers.
 */
export async function getPdmWorkflows(): Promise<PdmWorkflow[]> {
  return webApi.get('/admin/settings/pdm/workflows')
}
