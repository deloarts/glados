import { onScopeDispose, watch } from 'vue'

import { useLiveStore } from '@/core/realtime/liveStore'

import { useAutoPlanRunStore } from '../stores/autoPlanRunStore'

/**
 * App-lifetime subscription to the auto-plan run live resource. Every
 * signal and every reconnect refetches the run status, so trigger buttons
 * stay correct whether or not a dialog is open. Call it once from an
 * app-lifetime scope; it also fetches once at call time.
 */
export function useAutoPlanRunLiveSync(): void {
  const liveStore = useLiveStore()
  const autoPlanRunStore = useAutoPlanRunStore()

  const unsubscribe = liveStore.on('auto-plan-run', () => {
    void autoPlanRunStore.fetchStatus()
  })

  watch(
    () => liveStore.reconnectCount,
    () => {
      void autoPlanRunStore.fetchStatus()
    },
  )

  void autoPlanRunStore.fetchStatus()

  onScopeDispose(() => {
    unsubscribe()
  })
}
