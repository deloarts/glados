import { webApi } from '@/core/api/webRequest'
import type { CalculationResponse } from '../types/calculation'

/** Links a draft calculation to a device of its product; null unlinks it. */
export function setCalculationDevice(calculationId: number, deviceId: number | null): Promise<CalculationResponse> {
  return webApi.put('/calculations/{calculation_id}/device', {
    path: { calculation_id: calculationId },
    body: { product_device_id: deviceId },
  })
}
