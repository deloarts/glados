<script setup lang="ts">
import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

const props = defineProps<{
  item: BoughtItemResponse
}>()

const emit = defineEmits<{
  click: [event: Event, id: number]
}>()

function onClick(event: Event): void {
  if (props.item.successor_item_id) emit('click', event, props.item.successor_item_id)
}
</script>

<template>
  <div class="successor-cell">
    <Tag
      v-if="item.successor_item_id"
      :value="`#${item.successor_item_id}`"
      severity="secondary"
      class="successor-tag"
      role="button"
      tabindex="0"
      @click.stop="onClick"
      @keydown.enter="onClick"
      @keydown.space.prevent="onClick"
    />
  </div>
</template>

<style scoped lang="scss">
.successor-tag {
  cursor: pointer;

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
}
</style>
