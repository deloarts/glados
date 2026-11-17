import { postFile } from '@/core/api/postFile'

import type { UserResponse } from '@/core/types/userResponse'

export async function uploadUserAvatar(userId: number, file: File): Promise<UserResponse> {
  return (await postFile('/users/{user_id}/avatar', file, {
    path: { user_id: userId },
  })) as UserResponse
}
