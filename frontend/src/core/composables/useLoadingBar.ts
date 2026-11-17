import { onUnmounted, watch } from 'vue'
import type { WatchSource } from 'vue'

import { useLoadingBarStore } from '@/core/stores/loadingBarStore'

/**
 * Feeds a local loading source (a store's `loading` ref, etc.) into the
 * global header loading bar. Tracks whether it currently holds a `start()`
 * so an unmount mid-load still balances with a `stop()`.
 */
export function watchLoadingBar(source: WatchSource<boolean>) {
  const loadingBarStore = useLoadingBarStore()
  let active = false

  watch(
    source,
    (value) => {
      if (value && !active) {
        active = true
        loadingBarStore.start()
      } else if (!value && active) {
        active = false
        loadingBarStore.stop()
      }
    },
    { immediate: true },
  )

  onUnmounted(() => {
    if (active) {
      active = false
      loadingBarStore.stop()
    }
  })
}
