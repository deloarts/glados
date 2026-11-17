import { postFile } from '@/core/api/postFile'

import type { UserResponse } from '@/core/types/userResponse'

export async function uploadAvatar(file: File): Promise<UserResponse> {
  return (await postFile('/users/me/avatar', file)) as UserResponse
}
