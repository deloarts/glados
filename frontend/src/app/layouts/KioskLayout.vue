<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

// The bare shell of a wall display and of the infoscreen preview: the whole
// viewport, no sidebar, header, search or links, and nothing that scrolls.
// On the device routes, which open without a web session, the pointer is
// hidden as well, since nobody operates a wall display with a mouse.
const route = useRoute()
const hidesCursor = computed(() => route.meta.requiresAuth === false)
</script>

<template>
  <div class="kiosk-layout" :class="{ 'kiosk-layout--no-cursor': hidesCursor }">
    <RouterView />
  </div>
</template>

<style scoped lang="scss">
.kiosk-layout {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: var(--p-content-background);
  color: var(--p-text-color);
}

.kiosk-layout--no-cursor,
.kiosk-layout--no-cursor :deep(*) {
  cursor: none;
}
</style>
