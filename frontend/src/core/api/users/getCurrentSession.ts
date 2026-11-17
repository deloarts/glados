import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'

export type CurrentSessionResult = Schemas['CurrentSessionResult']

export async function getCurrentSession(): Promise<CurrentSessionResult> {
  return webApi.get('/users/me/sessions/current')
}
