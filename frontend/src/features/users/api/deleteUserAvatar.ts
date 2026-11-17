import { webApi } from '@/core/api/webRequest'

import type { UserResponse } from '@/core/types/userResponse'

export async function deleteUserAvatar(userId: number): Promise<UserResponse> {
  return webApi.delete('/users/{user_id}/avatar', {
    path: { user_id: userId },
  })
}
