<!--
  One row of an Overview tab's Related block: what is related, how many, and
  tags that break the number down. Clicking it opens the tab that lists them.
-->
<script setup lang="ts">
defineProps<{
  label: string
  count: string | number
}>()

defineEmits<{ click: [] }>()
</script>

<template>
  <button type="button" class="related-row" @click="$emit('click')">
    <span class="related-label">{{ label }}</span>
    <slot />
    <span class="related-count" data-testid="related-count">{{ count }}</span>
    <i class="mdi mdi-chevron-right related-chevron" aria-hidden="true" />
  </button>
</template>

<style scoped lang="scss">
.related-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  width: 100%;
  min-height: 2.75rem;
  padding: var(--space-2) var(--space-3);
  border: 0;
  border-top: 1px solid var(--p-content-border-color);
  border-radius: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;

  &:hover {
    background: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: 2px solid var(--p-primary-color);
    outline-offset: -2px;
  }
}

.related-label {
  flex: 1;
}

.related-count {
  min-width: 1.5rem;
  text-align: right;
  font-weight: 600;
}

.related-chevron {
  color: var(--p-text-muted-color);
}
</style>
