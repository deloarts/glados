import { webApi } from '@/core/api/webRequest'

import type { UserUpdateRequest } from '@/core/types/userRequest'
import type { UserResponse } from '@/core/types/userResponse'

export async function updateCurrentUser(payload: UserUpdateRequest): Promise<UserResponse> {
  return webApi.put('/users/me', { body: payload })
}
