<script lang="ts">
import { defineComponent, onUnmounted, watch } from 'vue'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLiveStore } from '@/core/realtime/liveStore'

// No template, no toggle, no banner. Live row-sync is always on and
// silent per design. This component only owns the connection's lifetime:
// open while a user is authenticated, closed otherwise (a logged-out tab
// has no token to send and nothing to receive for). `render: () => null`
// (rather than a `<template>` block) so it renders nothing without a
// dummy root node just to satisfy vue/valid-template-root.
export default defineComponent({
  name: 'LiveConnectionHandler',
  setup() {
    const currentUserStore = useCurrentUserStore()
    const liveStore = useLiveStore()

    watch(
      () => currentUserStore.isAuthenticated,
      (isAuthenticated) => {
        if (isAuthenticated) liveStore.start()
        else liveStore.stop()
      },
      { immediate: true },
    )

    onUnmounted(() => {
      liveStore.stop()
    })
  },
  render() {
    return null
  },
})
</script>
