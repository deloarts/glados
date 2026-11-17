import { webApi } from '@/core/api/webRequest'

import type { UserResponse } from '@/core/types/userResponse'

export async function deleteAvatar(): Promise<UserResponse> {
  return webApi.delete('/users/me/avatar')
}
