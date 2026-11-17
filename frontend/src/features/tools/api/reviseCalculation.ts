import { webApi } from '@/core/api/webRequest'
import type { CalculationResponse } from '../types/calculation'

/** Starts the next revision of a released calculation and returns it. */
export async function reviseCalculation(id: number, reason: string): Promise<CalculationResponse> {
  const calculation = await webApi.post('/calculations/{calculation_id}/revise', {
    path: { calculation_id: id },
    body: { reason },
  })
  return { ...calculation, changes: calculation.changes ?? [] }
}
