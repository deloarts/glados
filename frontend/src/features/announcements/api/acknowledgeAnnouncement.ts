import { webApi } from '@/core/api/webRequest'

/**
 * Idempotent: acknowledging an already-acknowledged announcement still
 * returns 204 rather than erroring, so a retry after a dropped response is
 * always safe.
 */
export async function acknowledgeAnnouncement(publicId: string): Promise<void> {
  await webApi.post('/announcements/acknowledgements/{public_id}/acknowledge', {
    path: { public_id: publicId },
  })
}
