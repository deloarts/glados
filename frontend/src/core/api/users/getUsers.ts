import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { UserFilterDto } from '@/core/types/userRequest'
import type { UserResponse } from '@/core/types/userResponse'

export async function getUsers(params?: UserFilterDto): Promise<PageResponse<UserResponse>> {
  return webApi.get('/users/', { query: params })
}
