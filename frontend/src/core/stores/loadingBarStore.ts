import { defineStore } from 'pinia'
import { ref } from 'vue'

// Once shown, keep the bar visible for at least this long so a fast
// load doesn't just flicker on and off.
const MIN_VISIBLE_MS = 1200

export const useLoadingBarStore = defineStore('loadingBar', () => {
  const pendingCount = ref(0)
  const isLoading = ref(false)

  let shownAt = 0
  let hideTimeout: ReturnType<typeof setTimeout> | null = null

  function start() {
    pendingCount.value++
    if (pendingCount.value === 1) {
      if (hideTimeout) {
        clearTimeout(hideTimeout)
        hideTimeout = null
      }
      shownAt = Date.now()
      isLoading.value = true
    }
  }

  function stop() {
    pendingCount.value = Math.max(0, pendingCount.value - 1)
    if (pendingCount.value !== 0) return

    const remaining = MIN_VISIBLE_MS - (Date.now() - shownAt)
    if (remaining <= 0) {
      isLoading.value = false
      return
    }

    hideTimeout = setTimeout(() => {
      hideTimeout = null
      if (pendingCount.value === 0) isLoading.value = false
    }, remaining)
  }

  return { isLoading, start, stop }
})
