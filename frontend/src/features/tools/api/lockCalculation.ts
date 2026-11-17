import { webApi } from '@/core/api/webRequest'
import type { CalculationResponse } from '../types/calculation'

/** Takes the edit lock, or renews the one the caller holds; `takeOver` takes it from another editor. */
export async function lockCalculation(id: number, takeOver = false): Promise<CalculationResponse> {
  const calculation = await webApi.post('/calculations/{calculation_id}/lock', {
    path: { calculation_id: id },
    body: { take_over: takeOver },
  })
  return { ...calculation, changes: calculation.changes ?? [] }
}

/** Ends the edit lock the caller holds; `force` ends anyone's, which needs the manage permission. */
export async function unlockCalculation(id: number, force = false): Promise<CalculationResponse> {
  const calculation = await webApi.delete('/calculations/{calculation_id}/lock', { path: { calculation_id: id }, query: { force } })
  return { ...calculation, changes: calculation.changes ?? [] }
}
