/**
 * The pictures of an order's delivery rows, such as photos of damaged goods.
 * They are order files of the picture category that name their delivery
 * row, so they come from the order files store and also show up among the
 * order's own files. Uploading needs only receive:deliveries.
 */
import { computed, type Ref } from 'vue'

import { uploadDeliveryPicture } from '../api/uploadDeliveryPicture'
import { useOrderFilesStore } from '../stores/orderFilesStore'
import type { OrderFile } from '../types/ordersResponse'

export function useDeliveryPictures(orderId: Ref<number | null>) {
  const filesStore = useOrderFilesStore()

  const pictures = computed<OrderFile[]>(() =>
    orderId.value === null
      ? []
      : filesStore.getFiles(orderId.value).filter((file) => file.delivery_id != null),
  )

  function picturesOf(deliveryId: number): OrderFile[] {
    return pictures.value.filter((file) => file.delivery_id === deliveryId)
  }

  async function load(): Promise<void> {
    if (orderId.value !== null) await filesStore.fetchFiles(orderId.value)
  }

  /**
   * Uploads every file to the row and reads the order's files again once.
   * Returns how many uploads failed, so the caller can say so.
   */
  async function upload(orderItemId: number, deliveryId: number, files: File[]): Promise<number> {
    const id = orderId.value
    if (id === null || files.length === 0) return 0
    let failed = 0
    for (const file of files) {
      try {
        await uploadDeliveryPicture(id, orderItemId, deliveryId, file)
      } catch {
        failed += 1
      }
    }
    await filesStore.refetchFiles(id)
    return failed
  }

  async function remove(fileId: number): Promise<void> {
    if (orderId.value !== null) await filesStore.remove(orderId.value, fileId)
  }

  return { pictures, picturesOf, load, upload, remove }
}
