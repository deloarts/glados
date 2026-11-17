import axios from 'axios'

import { webApi } from '@/core/api/webRequest'

export async function getUserAvatar(userId: number): Promise<Blob | null> {
  try {
    // The schema declares no body type for an image route, so the blob is cast.
    return (await webApi.get('/users/{user_id}/avatar', {
      path: { user_id: userId },
      config: { responseType: 'blob' },
    })) as Blob
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null
    }
    throw error
  }
}
