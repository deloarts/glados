import { webApi } from '@/core/api/webRequest'
import type { Acknowledgement } from '../types/acknowledgementTypes'

/**
 * The only field editable after creation: text/severity/recipients are
 * immutable (a changed text would invalidate earlier confirmations, see
 * acknowledgementTypes.ts), so this is the one PATCH the API offers.
 */
export async function setAcknowledgementEnabled(
  publicId: string,
  enabled: boolean,
): Promise<Acknowledgement> {
  return webApi.patch('/admin/acknowledgements/{public_id}', {
    path: { public_id: publicId },
    body: {
      enabled,
    },
  })
}
