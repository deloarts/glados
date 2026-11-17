import { webApi } from '@/core/api/webRequest'

import type { ResolvePublicIdResponse } from '../types/resolvePublicIdResponse'

export async function resolvePublicId(publicId: string): Promise<ResolvePublicIdResponse> {
  return webApi.get('/resolve/{public_id}', { path: { public_id: publicId } })
}
