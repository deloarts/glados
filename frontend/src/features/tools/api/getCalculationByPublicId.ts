import { webApi } from '@/core/api/webRequest'
import type { CalculationResponse } from '../types/calculation'

export async function getCalculationByPublicId(publicId: string): Promise<CalculationResponse> {
  const calculation = await webApi.get('/calculations/by-public-id/{public_id}', {
    path: { public_id: publicId },
  })
  return { ...calculation, changes: calculation.changes ?? [] }
}
