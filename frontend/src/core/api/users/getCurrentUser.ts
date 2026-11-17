import { webApi } from '@/core/api/webRequest'

import type { UserResponse } from '@/core/types/userResponse'

export async function getCurrentUser(): Promise<UserResponse> {
  return webApi.get('/users/me')
}
