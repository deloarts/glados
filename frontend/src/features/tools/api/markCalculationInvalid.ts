import { webApi } from '@/core/api/webRequest'
import type { CalculationResponse } from '../types/calculation'

/** Marks a released revision invalid; it stays released and on record. */
export async function markCalculationInvalid(id: number, reason: string): Promise<CalculationResponse> {
  const calculation = await webApi.post('/calculations/{calculation_id}/mark-invalid', {
    path: { calculation_id: id },
    body: { reason },
  })
  return { ...calculation, changes: calculation.changes ?? [] }
}
