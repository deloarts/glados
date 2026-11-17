import { webApi } from '@/core/api/webRequest'
import type { PageResponse } from '@/core/api/types'
import type {
  PdmReconciliationFinding,
  PdmReconciliationFindingFilterParams,
} from '../types/adminSettingsTypes'

/**
 * Paged, filtered findings of the latest reconciliation report, for the
 * admin reconciliation dialog's findings table.
 */
export async function getPdmReconciliationFindings(
  params?: PdmReconciliationFindingFilterParams,
): Promise<PageResponse<PdmReconciliationFinding>> {
  // kind is narrowed to the closed union, see PdmReconciliationFinding.
  return webApi.get('/admin/settings/pdm/reconciliation/findings', {
    query: params,
  }) as Promise<PageResponse<PdmReconciliationFinding>>
}
