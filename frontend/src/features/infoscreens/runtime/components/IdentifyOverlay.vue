<script setup lang="ts">
// Covers the whole display with its own name and, when set, where it hangs
// for a few seconds, so whoever pressed Identify in Glados finds the right
// screen in the hall.
withDefaults(defineProps<{ name: string; location?: string | null }>(), { location: null })
</script>

<template>
  <div class="identify-overlay" role="status" data-testid="identify-overlay">
    <i class="mdi mdi-monitor-eye identify-overlay-icon" aria-hidden="true" />
    <span class="identify-overlay-name">{{ name }}</span>
    <span v-if="location" class="identify-overlay-location" data-testid="identify-overlay-location">
      {{ location }}
    </span>
  </div>
</template>

<style scoped lang="scss">
.identify-overlay {
  position: fixed;
  inset: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4vmin;
  padding: 6vmin;
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
  text-align: center;
}

.identify-overlay-icon {
  font-size: clamp(4rem, 18vmin, 18rem);
  line-height: 1;
}

.identify-overlay-name {
  font-size: clamp(3rem, 14vmin, 16rem);
  font-weight: 800;
  line-height: 1.1;
  overflow-wrap: anywhere;
}

.identify-overlay-location {
  max-width: 90%;
  font-size: clamp(1.6rem, 6vmin, 7rem);
  font-weight: 600;
  line-height: 1.2;
  opacity: 0.85;
  overflow-wrap: anywhere;
}
</style>
