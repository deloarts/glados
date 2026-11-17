import { computed, onScopeDispose, ref, watch } from 'vue'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'

/**
 * Drives the header countdown next to the avatar button, counting down to
 * `currentUserStore.sessionExpiresAt` (system users only: the hard
 * 15-minute session lifetime).
 *
 * `remainingSeconds` is recomputed from the wall clock on every tick rather
 * than decremented, so a tab put to sleep and woken later catches up to the
 * real remaining time instead of resuming a stale countdown. The 1s
 * interval only runs while an expiry is set, and calls
 * `userStore.sessionExpired()` exactly once per expiry value the instant it
 * reaches zero, the same path the API's 401 interceptor uses, so the
 * client-side clock (already skew-corrected in the store) is what forces
 * the redirect rather than waiting on the next failed request.
 */
export function useSessionCountdown() {
  const userStore = useCurrentUserStore()

  const now = ref(Date.now())
  let intervalId: ReturnType<typeof setInterval> | undefined
  let expiredNotified = false

  function stopInterval() {
    if (intervalId === undefined) return
    clearInterval(intervalId)
    intervalId = undefined
  }

  function startInterval() {
    if (intervalId !== undefined) return
    now.value = Date.now()
    intervalId = setInterval(() => {
      now.value = Date.now()
    }, 1000)
  }

  watch(
    () => userStore.sessionExpiresAt,
    (expiresAt) => {
      expiredNotified = false
      if (expiresAt === null) {
        stopInterval()
        return
      }
      startInterval()
    },
    { immediate: true },
  )

  const remainingSeconds = computed(() => {
    const expiresAt = userStore.sessionExpiresAt
    if (expiresAt === null) return 0
    return Math.max(0, Math.ceil((expiresAt - now.value) / 1000))
  })

  watch(remainingSeconds, (seconds) => {
    if (seconds !== 0 || userStore.sessionExpiresAt === null || expiredNotified) return
    expiredNotified = true
    userStore.sessionExpired()
  })

  const isActive = computed(() => userStore.sessionExpiresAt !== null)
  const isWarning = computed(() => isActive.value && remainingSeconds.value < 60)

  const label = computed(() => {
    const total = remainingSeconds.value
    const minutes = Math.floor(total / 60)
    const seconds = total % 60
    return `${minutes}:${String(seconds).padStart(2, '0')}`
  })

  onScopeDispose(() => {
    stopInterval()
  })

  return { remainingSeconds, label, isActive, isWarning }
}
