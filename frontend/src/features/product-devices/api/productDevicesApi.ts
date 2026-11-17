import { webApi } from '@/core/api/webRequest'
import type {
  ProductDevice,
  ProductDeviceNamePreview,
  ProductDeviceNamePreviewRequest,
  ProductDeviceSaveRequest,
} from '../types/productDevice'

export function getProductDevices(
  productId: number,
  includeArchived: boolean,
): Promise<ProductDevice[]> {
  return webApi.get('/products/{product_id}/devices', {
    path: { product_id: productId },
    query: { include_archived: includeArchived },
  })
}

export function createProductDevice(
  productId: number,
  body: ProductDeviceSaveRequest,
): Promise<ProductDevice> {
  return webApi.post('/products/{product_id}/devices', { path: { product_id: productId }, body })
}

/** Saves an edited device; one changed since `expectedEditVersion` was read answers 409. */
export function updateProductDevice(
  deviceId: number,
  expectedEditVersion: number,
  body: ProductDeviceSaveRequest,
): Promise<ProductDevice> {
  return webApi.put('/product-devices/{device_id}', {
    path: { device_id: deviceId },
    body: { ...body, expected_edit_version: expectedEditVersion },
  })
}

export function setProductDeviceArchived(
  deviceId: number,
  archived: boolean,
): Promise<ProductDevice> {
  return archived
    ? webApi.post('/product-devices/{device_id}/archive', { path: { device_id: deviceId } })
    : webApi.post('/product-devices/{device_id}/restore', { path: { device_id: deviceId } })
}

export function previewProductDeviceName(
  productId: number,
  body: ProductDeviceNamePreviewRequest,
): Promise<ProductDeviceNamePreview> {
  return webApi.post('/products/{product_id}/devices/name-preview', {
    path: { product_id: productId },
    body,
  })
}
