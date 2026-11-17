import { webApi } from '@/core/api/webRequest'
import type { InvokePdmOperationCommand, PdmInvokeResult } from '../types/adminSettingsTypes'

/**
 * Invokes one catalogued PDM Web API operation under the saved connection
 * and its shared session, for the admin API console.
 *
 * Rejects with 400 when `operationId` is a mutating operation invoked
 * without `cmd.allow_mutating`, 404 for an unknown operation id, and
 * 502/503 when the vault itself errors or cannot be reached.
 */
export async function invokePdmOperation(
  operationId: string,
  cmd: InvokePdmOperationCommand,
): Promise<PdmInvokeResult> {
  return webApi.post('/admin/settings/pdm/operations/{operation_id}/invoke', {
    path: { operation_id: operationId },
    body: cmd,
  })
}
