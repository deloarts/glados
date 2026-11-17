import { webApi } from '@/core/api/webRequest'
import type { PdmConnectionTestResult, VerifyPdmConnectionCommand } from '../types/adminSettingsTypes'

/**
 * Probes the SOLIDWORKS PDM Web API with the supplied (not-yet-saved)
 * connection settings: an unauthenticated version() call followed by
 * authenticate().
 *
 * 200 on success. Rejects with 400 when the connection is incomplete or the
 * vault refuses the credentials, and 503 when the server cannot be reached
 * at all: the caller should keep those apart, they need different fixes.
 * Nothing is persisted either way, even on success.
 */
export async function verifyPdmConnection(
  cmd: VerifyPdmConnectionCommand,
): Promise<PdmConnectionTestResult> {
  return webApi.post('/admin/settings/pdm/test', { body: cmd })
}
