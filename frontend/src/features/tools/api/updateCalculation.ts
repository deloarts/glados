import { webApi } from '@/core/api/webRequest'
import type { CalculationResponse, CalculationUpdateRequest } from '../types/calculation'

export async function updateCalculation(
  id: number,
  body: CalculationUpdateRequest,
): Promise<CalculationResponse> {
  const calculation = await webApi.put('/calculations/{calculation_id}', {
    path: { calculation_id: id },
    body,
  })
  return { ...calculation, changes: calculation.changes ?? [] }
}
