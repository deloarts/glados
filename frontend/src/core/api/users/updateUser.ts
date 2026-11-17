import { webApi } from '@/core/api/webRequest'

import type { UserUpdateRequest } from '@/core/types/userRequest'
import type { UserResponse } from '@/core/types/userResponse'

export async function updateUser(
  userId: number,
  payload: UserUpdateRequest,
): Promise<UserResponse> {
  return webApi.put('/users/{user_id}', {
    path: { user_id: userId },
    body: payload,
  })
}
