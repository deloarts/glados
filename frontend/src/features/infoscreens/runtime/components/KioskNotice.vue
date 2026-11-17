<script setup lang="ts">
// A full-screen message of a wall display: one icon, a title and a sentence,
// sized to be read from across a hall.
withDefaults(
  defineProps<{
    title: string
    text?: string | null
    icon?: string
    tone?: 'neutral' | 'warn' | 'danger'
  }>(),
  { text: null, icon: 'mdi mdi-monitor', tone: 'neutral' },
)
</script>

<template>
  <section class="kiosk-notice" :class="`kiosk-notice--${tone}`" role="status">
    <i :class="['kiosk-notice-icon', icon]" aria-hidden="true" />
    <h1 class="kiosk-notice-title">{{ title }}</h1>
    <p v-if="text" class="kiosk-notice-text">{{ text }}</p>
    <slot />
  </section>
</template>

<style scoped lang="scss">
.kiosk-notice {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(0.75rem, 2.5vmin, 2.5rem);
  padding: 6vmin 8vmin;
  text-align: center;
}

.kiosk-notice-icon {
  font-size: clamp(3rem, 12vmin, 12rem);
  line-height: 1;
  color: var(--p-text-muted-color);
}

.kiosk-notice--warn .kiosk-notice-icon {
  color: var(--p-orange-500);
}

.kiosk-notice--danger .kiosk-notice-icon {
  color: var(--p-red-500);
}

.kiosk-notice-title {
  margin: 0;
  font-size: clamp(1.8rem, 6vmin, 6rem);
  font-weight: 700;
  line-height: 1.15;
}

.kiosk-notice-text {
  margin: 0;
  max-width: 60ch;
  font-size: clamp(1.1rem, 3vmin, 3rem);
  line-height: 1.35;
  color: var(--p-text-muted-color);
}
</style>
