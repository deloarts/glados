<script setup lang="ts">
import { useI18n } from 'vue-i18n'

/**
 * The draggable edge between a side panel and the content, from
 * `useResizablePanelWidth`. It is a focusable separator, so a keyboard user
 * resizes the panel with the arrow keys, Home and End, and a screen reader
 * announces the width. A mouse drag starts on mousedown as before.
 */
withDefaults(
  defineProps<{
    width: number
    min: number
    max?: number
    label?: string
  }>(),
  { max: undefined, label: undefined },
)

const emit = defineEmits<{
  start: [event: MouseEvent]
  key: [event: KeyboardEvent]
}>()

const { t } = useI18n()

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/no-static-element-interactions -- a focusable separator is the ARIA window splitter, which the rule does not count as a widget */
</script>

<template>
  <div
    class="resize-handle-ew"
    role="separator"
    aria-orientation="vertical"
    tabindex="0"
    :aria-label="label ?? t('common.resizePanel')"
    :aria-valuenow="Math.round(width)"
    :aria-valuemin="min"
    :aria-valuemax="max"
    @mousedown.prevent="emit('start', $event)"
    @keydown="emit('key', $event)"
  />
</template>

<style scoped lang="scss">
.resize-handle-ew {
  flex-shrink: 0;
  width: 8px;
  cursor: ew-resize;
  display: flex;
  justify-content: center;
  padding: var(--space-4) 0;

  &::after {
    content: '';
    display: block;
    height: 100%;
    width: 2px;
    border-radius: 1px;
    background: var(--p-content-border-color);
    transition: background 0.15s;
  }

  &:hover::after,
  &:active::after,
  &:focus-visible::after {
    background: var(--p-primary-color);
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}
</style>
