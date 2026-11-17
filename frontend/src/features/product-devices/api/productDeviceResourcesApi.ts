import { webApi } from '@/core/api/webRequest'
import type { ListPlaceTarget } from '@/shared/types/listOrder'
import type {
  ProductDeviceKind,
  ProductDeviceKindSaveRequest,
  ProductDeviceOption,
  ProductDeviceOptionCreateRequest,
  ProductDeviceOptionUpdateRequest,
} from '../types/productDevice'

/** Every entry of the plain device lists, archived ones included. */
export function getProductDeviceOptions(): Promise<ProductDeviceOption[]> {
  return webApi.get('/product-device-resources/options', { query: { include_archived: true } })
}

export function createProductDeviceOption(
  body: ProductDeviceOptionCreateRequest,
): Promise<ProductDeviceOption> {
  return webApi.post('/product-device-resources/options', { body })
}

export function updateProductDeviceOption(
  id: number,
  body: ProductDeviceOptionUpdateRequest,
): Promise<ProductDeviceOption> {
  return webApi.put('/product-device-resources/options/{option_id}', {
    path: { option_id: id },
    body,
  })
}

export function setProductDeviceOptionArchived(
  id: number,
  archived: boolean,
): Promise<ProductDeviceOption> {
  return archived
    ? webApi.post('/product-device-resources/options/{option_id}/archive', {
        path: { option_id: id },
      })
    : webApi.post('/product-device-resources/options/{option_id}/restore', {
        path: { option_id: id },
      })
}

/**
 * Puts an entry next to another one of its category, as dragging its row
 * does, and returns the whole category, archived entries included, in its
 * new order.
 */
export function placeProductDeviceOption(
  id: number,
  target: ListPlaceTarget,
): Promise<ProductDeviceOption[]> {
  return webApi.post('/product-device-resources/options/{option_id}/place', {
    path: { option_id: id },
    body: target,
  })
}

/** Every device kind with its positions and parameters, archived ones included. */
export function getProductDeviceKinds(): Promise<ProductDeviceKind[]> {
  return webApi.get('/product-device-resources/kinds', { query: { include_archived: true } })
}

export function createProductDeviceKind(
  body: ProductDeviceKindSaveRequest,
): Promise<ProductDeviceKind> {
  return webApi.post('/product-device-resources/kinds', { body })
}

export function updateProductDeviceKind(
  id: number,
  body: ProductDeviceKindSaveRequest,
): Promise<ProductDeviceKind> {
  return webApi.put('/product-device-resources/kinds/{kind_id}', { path: { kind_id: id }, body })
}

export function setProductDeviceKindArchived(
  id: number,
  archived: boolean,
): Promise<ProductDeviceKind> {
  return archived
    ? webApi.post('/product-device-resources/kinds/{kind_id}/archive', { path: { kind_id: id } })
    : webApi.post('/product-device-resources/kinds/{kind_id}/restore', { path: { kind_id: id } })
}

/** Puts a kind next to another one, as dragging its row does, and returns every kind in the new order. */
export function placeProductDeviceKind(
  id: number,
  target: ListPlaceTarget,
): Promise<ProductDeviceKind[]> {
  return webApi.post('/product-device-resources/kinds/{kind_id}/place', {
    path: { kind_id: id },
    body: target,
  })
}
