import type { Schemas } from '@/core/api/generated'
import { postFile } from '@/core/api/postFile'
import { webApi } from '@/core/api/webRequest'
import { createOwnerFilesApi } from '@/shared/api/createFilesApi'

/**
 * The product's files as far as devices use them: each device's rendering
 * and parent assembly rendering, and the product's single top-down overview
 * the device markers sit on. They are product files of their own
 * categories; a device's two images are set through the device, which
 * replaces the previous file of the slot.
 */
export type DeviceImageFile = Schemas['ProductFileResponse']
export type DeviceImageSlot = Schemas['ProductDeviceImageSlot']
export type DeviceImageCategory = 'device_rendering' | 'device_assembly'

/**
 * A device image as the shared files section handles it: the product file
 * plus the device it belongs to.
 */
export type DeviceSlotFile = DeviceImageFile & { device_id: number; category: DeviceImageCategory }

const productFiles = createOwnerFilesApi<{
  file: DeviceImageFile
  category: Schemas['ProductFileCategory']
}>('product')

export const SLOT_OF_CATEGORY: Record<DeviceImageCategory, DeviceImageSlot> = {
  device_rendering: 'rendering',
  device_assembly: 'assembly',
}

export async function getDeviceImageFiles(productId: number): Promise<DeviceImageFile[]> {
  const files = await productFiles.list(productId)
  return files.filter(
    (file) =>
      file.category === 'device_rendering' ||
      file.category === 'device_assembly' ||
      file.category === 'device_overview',
  )
}

export function uploadDeviceOverview(productId: number, file: File): Promise<DeviceImageFile> {
  return productFiles.upload(productId, file, 'device_overview')
}

export function getDeviceImageBlob(productId: number, fileId: number): Promise<Blob> {
  return productFiles.getBlob(productId, fileId)
}

/** The device's current images, read from its product's files. */
export async function getDeviceSlotFiles(deviceId: number): Promise<DeviceSlotFile[]> {
  const device = await webApi.get('/product-devices/{device_id}', { path: { device_id: deviceId } })
  const wanted = new Map<number | null, DeviceImageCategory>([
    [device.rendering_file_id, 'device_rendering'],
    [device.assembly_file_id, 'device_assembly'],
  ])
  const files = await productFiles.list(device.product_id)
  return files
    .filter((file) => file.id !== null && wanted.has(file.id))
    .map((file) => ({ ...file, device_id: deviceId, category: wanted.get(file.id)! }))
}

/** Uploads into a slot, replacing its previous image, and returns the new file. */
export async function uploadDeviceSlotFile(
  deviceId: number,
  file: File,
  category: DeviceImageCategory,
): Promise<DeviceSlotFile> {
  await postFile('/product-devices/{device_id}/images/{slot}', file, {
    path: { device_id: deviceId, slot: SLOT_OF_CATEGORY[category] },
  })
  const files = await getDeviceSlotFiles(deviceId)
  const uploaded = files.find((f) => f.category === category)
  if (!uploaded) throw new Error('The uploaded image is missing from the device.')
  return uploaded
}

/** Empties the slot that holds `fileId`. */
export async function removeDeviceSlotFile(deviceId: number, fileId: number): Promise<void> {
  const files = await getDeviceSlotFiles(deviceId)
  const file = files.find((f) => f.id === fileId)
  if (!file) return
  await webApi.delete('/product-devices/{device_id}/images/{slot}', {
    path: { device_id: deviceId, slot: SLOT_OF_CATEGORY[file.category] },
  })
}
