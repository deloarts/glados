import { webApi } from '@/core/api/webRequest'
import type { CalculationSummaryResponse } from '../types/calculation'

/** Every revision of the calculation's lineage, newest first. */
export async function getCalculationRevisions(id: number): Promise<CalculationSummaryResponse[]> {
  return webApi.get('/calculations/{calculation_id}/revisions', { path: { calculation_id: id } })
}
