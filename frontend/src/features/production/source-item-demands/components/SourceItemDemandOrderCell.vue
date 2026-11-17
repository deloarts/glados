<script setup lang="ts">
// The Order cell of the source item demands table: a tag per order the
// demand's allocations sit on, each opening its order, and the open quote
// requests asking for the demand.
import { computed } from 'vue'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { InQuotationTag } from '@/features/quote-requests'
import { useSourceItemsAllocationsStore } from '../stores/sourceItemsAllocationsStore'

import type { OpenQuoteRequestRef } from '@/features/quote-requests'

const props = defineProps<{
  demandId: number
  quoteRequests: OpenQuoteRequestRef[] | undefined
}>()

const emit = defineEmits<{
  openOrder: [orderId: number]
}>()

const allocationsStore = useSourceItemsAllocationsStore()

const orderTags = computed<{ id: number; label: string }[]>(() => {
  const summary = allocationsStore.getSummary(props.demandId)
  if (!summary) return []
  return (summary.order_ids ?? []).map((id, idx) => ({
    id,
    label: summary.order_numbers?.[idx] ?? `#${id}`,
  }))
})
</script>

<template>
  <div v-if="orderTags.length || quoteRequests" class="order-tags">
    <Tag
      v-for="tag in orderTags"
      :key="tag.id"
      :value="tag.label"
      severity="secondary"
      class="order-tag"
      role="button"
      tabindex="0"
      @click.stop="emit('openOrder', tag.id)"
      @keydown.enter="emit('openOrder', tag.id)"
      @keydown.space.prevent="emit('openOrder', tag.id)"
    />
    <InQuotationTag :requests="quoteRequests" />
  </div>
  <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
</template>

<style scoped lang="scss">
.order-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.order-tag {
  cursor: pointer;

  &:hover {
    opacity: 0.75;
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
}

.muted {
  color: var(--p-text-muted-color);
}
</style>
