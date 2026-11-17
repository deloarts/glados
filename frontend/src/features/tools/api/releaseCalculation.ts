import { webApi } from '@/core/api/webRequest'
import type { CalculationResponse } from '../types/calculation'

export async function releaseCalculation(id: number): Promise<CalculationResponse> {
  const calculation = await webApi.post('/calculations/{calculation_id}/release', {
    path: { calculation_id: id },
  })
  return { ...calculation, changes: calculation.changes ?? [] }
}
