import { getOrderFileBlob } from './getOrderFileBlob'
import { downloadBlob } from '@/core/utils/downloadBlob'

export async function downloadOrderAttachment(
  orderId: number,
  fileId: number,
  filename: string,
): Promise<void> {
  downloadBlob(await getOrderFileBlob(orderId, fileId), filename)
}
