import { onScopeDispose, ref } from 'vue'

/**
 * The current time, refreshed on the device every `intervalMs`, for the
 * clocks that tick locally instead of waiting for the feed.
 */
export function useTickingNow(intervalMs = 1000) {
  const now = ref(new Date())
  const timer = setInterval(() => {
    now.value = new Date()
  }, intervalMs)
  onScopeDispose(() => clearInterval(timer))
  return now
}
