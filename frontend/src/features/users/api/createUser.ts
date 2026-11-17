import { webApi } from '@/core/api/webRequest'

import type { UserCreateRequest } from '@/core/types/userRequest'
import type { UserResponse } from '@/core/types/userResponse'

export async function createUser(payload: UserCreateRequest): Promise<UserResponse> {
  return webApi.post('/users/', { body: payload })
}
