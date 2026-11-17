import { reactive } from 'vue'
import { defineStore } from 'pinia'

import { getUserAvatar } from '@/core/api/users/getUserAvatar'

export const useUserAvatarsStore = defineStore('userAvatars', () => {
  // Keyed by user id. Cached as blob object URLs so <img> tags don't need
  // to attach the Authorization header themselves.

  const urls = reactive(new Map<number, string>())
  const pending = new Map<number, Promise<string | null>>()

  function get(userId: number): string | null {
    return urls.get(userId) ?? null
  }

  async function fetch(userId: number): Promise<string | null> {
    const cached = urls.get(userId)
    if (cached) return cached

    const inFlight = pending.get(userId)
    if (inFlight) return inFlight

    const request = (async () => {
      const blob = await getUserAvatar(userId)
      if (!blob) return null

      const url = URL.createObjectURL(blob)
      urls.set(userId, url)
      return url
    })().finally(() => {
      pending.delete(userId)
    })

    pending.set(userId, request)
    return request
  }

  function invalidate(userId: number): void {
    const cached = urls.get(userId)
    if (cached) URL.revokeObjectURL(cached)
    urls.delete(userId)
    pending.delete(userId)
  }

  /**
   * Revokes every cached avatar; call on logout. Without this the blob
   * URLs from whoever the session belonged to just leak: nothing else ever
   * calls invalidate() for them, and the next sign-in fetches a fresh set
   * under a new URL rather than reusing these.
   */
  function clear(): void {
    for (const url of urls.values()) {
      URL.revokeObjectURL(url)
    }
    urls.clear()
    pending.clear()
  }

  return {
    get,
    fetch,
    invalidate,
    clear,
  }
})
