<script setup lang="ts">
import ProgressSpinner from 'openvue/progressspinner'

withDefaults(
  defineProps<{
    /**
     * Take the spinner out of the document flow and centre it on the viewport.
     *
     * Required wherever the async component is a child of a layout container
     * rather than page content: as an in-flow block it is a real flex/grid
     * item, so in `.app-shell` (a column flex container) it pushes the
     * footer up off the bottom of the screen for as long as the chunk takes to
     * arrive.
     */
    overlay?: boolean
  }>(),
  { overlay: false },
)
</script>

<template>
  <div class="async-chunk-loading" :class="{ 'is-overlay': overlay }">
    <ProgressSpinner style="width: 2rem; height: 2rem" stroke-width="4" />
  </div>
</template>

<style scoped>
.async-chunk-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
}

.async-chunk-loading.is-overlay {
  position: fixed;
  inset: 0;
  padding: 0;
  /* Below OpenVue's dialog layer (~1100). This is a placeholder for a dialog
     that is about to open, not something to sit on top of one. */
  z-index: 1000;
  pointer-events: none;
}
</style>
