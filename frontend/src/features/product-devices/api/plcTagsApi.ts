import { webApi } from '@/core/api/webRequest'
import type { Schemas } from '@/core/api/generated'
import type { PlcTagList } from '../types/productDevice'

/** The product's PLC tags for its PLC environment, built from its live devices. */
export function getProductPlcTags(productId: number): Promise<PlcTagList> {
  return webApi.get('/products/{product_id}/plc-tags', { path: { product_id: productId } })
}

export type ManualPlcTagSaveRequest = Schemas['ManualPlcTagSaveRequest']

/** Gives one signal a tag name of its own; null takes it off. */
export async function setSignalTagName(
  deviceId: number,
  componentId: number,
  signalIndex: number,
  tagName: string | null,
): Promise<void> {
  await webApi.put('/product-devices/{device_id}/signal-tag-name', {
    path: { device_id: deviceId },
    body: { component_id: componentId, signal_index: signalIndex, tag_name: tagName },
  })
}

export async function createManualPlcTag(productId: number, body: ManualPlcTagSaveRequest): Promise<void> {
  await webApi.post('/products/{product_id}/plc-tags/manual', { path: { product_id: productId }, body })
}

export async function updateManualPlcTag(tagId: number, body: ManualPlcTagSaveRequest): Promise<void> {
  await webApi.put('/plc-manual-tags/{tag_id}', { path: { tag_id: tagId }, body })
}

export async function deleteManualPlcTag(tagId: number): Promise<void> {
  await webApi.delete('/plc-manual-tags/{tag_id}', { path: { tag_id: tagId } })
}
