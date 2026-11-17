import { webApi } from '@/core/api/webRequest'
import type { DevicePlan, ProductDeviceCompleteness } from '../types/productDevice'

/** Per live device of the product: its plan ticks and its sequence coverage. */
export function getDeviceCompleteness(productId: number): Promise<ProductDeviceCompleteness[]> {
  return webApi.get('/products/{product_id}/device-completeness', { path: { product_id: productId } })
}

export async function setDeviceCheck(deviceId: number, plan: DevicePlan, checked: boolean): Promise<void> {
  await webApi.put('/product-devices/{device_id}/checks/{plan}', {
    path: { device_id: deviceId, plan },
    body: { checked },
  })
}
