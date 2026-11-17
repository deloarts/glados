<script lang="ts">
import { defineComponent, onUnmounted, watch } from 'vue'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLiveStore } from '@/core/realtime/liveStore'
import { LiveResource } from '@/core/realtime/resources'

import { useAnnouncementsStore } from '../stores/announcementsStore'

// Template-less handler keyed on auth state. Fetches /announcements/me on
// sign-in, on the live signal and on every reconnect, so a missed signal is
// caught up, and runs the store's window tick while signed in.
export default defineComponent({
  name: 'AnnouncementsHandler',
  setup() {
    const currentUserStore = useCurrentUserStore()
    const liveStore = useLiveStore()
    const announcementsStore = useAnnouncementsStore()

    let unsubscribe: (() => void) | null = null

    watch(
      () => currentUserStore.isAuthenticated,
      (isAuthenticated) => {
        if (isAuthenticated) {
          announcementsStore.startTicking()
          void announcementsStore.refresh()
          unsubscribe = liveStore.on(LiveResource.ANNOUNCEMENTS, () => {
            void announcementsStore.refresh()
          })
        } else {
          announcementsStore.stopTicking()
          unsubscribe?.()
          unsubscribe = null
        }
      },
      { immediate: true },
    )

    watch(
      () => liveStore.reconnectCount,
      () => {
        if (currentUserStore.isAuthenticated) void announcementsStore.refresh()
      },
    )

    onUnmounted(() => {
      announcementsStore.stopTicking()
      unsubscribe?.()
    })
  },
  render() {
    return null
  },
})
</script>
