import { webApi } from '@/core/api/webRequest'
import type { AcknowledgementRecipient } from '../types/acknowledgementTypes'

/**
 * Pending recipients first, then acknowledged, ordered by full_name: the
 * backend does the ordering.
 */
export async function getAcknowledgementRecipients(
  publicId: string,
): Promise<AcknowledgementRecipient[]> {
  return webApi.get('/admin/acknowledgements/{public_id}/recipients', {
    path: { public_id: publicId },
  })
}
