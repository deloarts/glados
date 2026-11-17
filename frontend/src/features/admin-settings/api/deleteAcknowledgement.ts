import { webApi } from '@/core/api/webRequest'

export async function deleteAcknowledgement(publicId: string): Promise<void> {
  await webApi.delete('/admin/acknowledgements/{public_id}', { path: { public_id: publicId } })
}
