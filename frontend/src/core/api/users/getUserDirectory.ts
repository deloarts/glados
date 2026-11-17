import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { UserDirectoryFilterDto } from '@/core/types/userRequest'
import type { UserSummary } from '@/core/types/userResponse'

/**
 * The reduced user list every signed-in user may read, for pickers and name
 * lookups. The full list with e-mail and permissions (getUsers) needs
 * read:settings.
 */
export async function getUserDirectory(
  params?: UserDirectoryFilterDto,
): Promise<PageResponse<UserSummary>> {
  return webApi.get('/users/directory', { query: params })
}
