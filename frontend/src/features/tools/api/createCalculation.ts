import { webApi } from '@/core/api/webRequest'
import type { CalculationCreateRequest, CalculationResponse } from '../types/calculation'

export async function createCalculation(
  body: CalculationCreateRequest,
): Promise<CalculationResponse> {
  const calculation = await webApi.post('/calculations', { body })
  return { ...calculation, changes: calculation.changes ?? [] }
}
