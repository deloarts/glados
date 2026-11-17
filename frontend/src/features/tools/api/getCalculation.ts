import { webApi } from '@/core/api/webRequest'
import type { CalculationResponse } from '../types/calculation'

export async function getCalculation(id: number): Promise<CalculationResponse> {
  const calculation = await webApi.get('/calculations/{calculation_id}', {
    path: { calculation_id: id },
  })
  return { ...calculation, changes: calculation.changes ?? [] }
}
