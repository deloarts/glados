<script setup lang="ts">
import { toRef } from 'vue'
import StatRing from './StatRing.vue'
import { useCountUp } from '../composables/useCountUp'

const props = defineProps<{
  label: string
  value: number
  icon?: string
  accentVar?: string
  ring?: { max: number; colorVar: string; trackColorVar: string }
  clickable?: boolean
  /**
   * Suppresses the number until the first response lands, so a cold dashboard
   * never shows a confident but false 0.
   */
  loading?: boolean
}>()

defineEmits<{ (e: 'click'): void }>()

const displayValue = useCountUp(toRef(props, 'value'))

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/no-static-element-interactions -- a button only when the tile is clickable, the role and tabindex are bound to that */
</script>

<template>
  <div
    class="stat-tile"
    :class="{ 'stat-tile--clickable': clickable }"
    :style="{ '--stat-tile-accent': accentVar ?? 'var(--p-primary-500)' }"
    :role="clickable ? 'button' : undefined"
    :tabindex="clickable ? 0 : undefined"
    @click="clickable && $emit('click')"
    @keydown.enter="clickable && $emit('click')"
    @keydown.space.prevent="clickable && $emit('click')"
  >
    <div class="stat-tile-icon" v-if="icon || ring">
      <StatRing
        v-if="ring"
        :value="loading ? 0 : value"
        :max="ring.max"
        :color-var="ring.colorVar"
        :track-color-var="ring.trackColorVar"
      />
      <i v-else-if="icon" :class="icon" aria-hidden="true" />
    </div>
    <div class="stat-tile-body">
      <Skeleton v-if="loading" width="2.5rem" height="1.6rem" class="stat-tile-skeleton" />
      <span v-else class="stat-tile-value">{{ displayValue }}</span>
      <span class="stat-tile-label">{{ label }}</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.stat-tile {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-4);
  border-radius: var(--p-content-border-radius);
  background: color-mix(in srgb, var(--p-content-background) 70%, transparent);
  backdrop-filter: blur(10px);
  border: 1px solid var(--p-content-border-color);
  box-shadow: var(--shadow-md);
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    inset: 0 auto 0 0;
    width: 3px;
    background: var(--stat-tile-accent);
  }
}

.stat-tile--clickable {
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}

.stat-tile-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 2.75rem;
  height: 2.75rem;

  i {
    font-size: var(--font-size-2xl);
    color: var(--stat-tile-accent);
  }
}

.stat-tile-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.stat-tile-value {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  font-family: var(--font-head);
  line-height: 1.1;
}

.stat-tile-label {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
