import { webApi } from '@/core/api/webRequest'

import type { InfoscreenFeedResponse } from '../types/infoscreenFeed'

/** The feed of a screen as a device would get it, read with the viewer's web session. */
export async function getInfoscreenPreviewFeed(infoscreenId: number): Promise<InfoscreenFeedResponse> {
  return webApi.get('/infoscreens/{infoscreen_id}/feed', { path: { infoscreen_id: infoscreenId } })
}
