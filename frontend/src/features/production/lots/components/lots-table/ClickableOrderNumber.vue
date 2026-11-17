<script setup lang="ts">
import { inject } from 'vue'

import { LOTS_TABLE_STEP_CONTEXT_KEY } from './lotsTableStepContext'

const props = defineProps<{
  orderId: number
  orderNumber: string
}>()

const ctx = inject(LOTS_TABLE_STEP_CONTEXT_KEY)

function open(): void {
  ctx?.openOrderDetail(props.orderId)
}
</script>

<template>
  <span class="order-link" role="button" tabindex="0" @click.stop="open" @keydown.enter="open">{{
    orderNumber
  }}</span>
</template>

<style scoped lang="scss">
// Inherits size/weight/colour from whatever sub-text line it sits in
// (.item-code in the step method cell, the delivery cell's own second
// line) so it reads as ordinary secondary text; only the hover state
// marks it as clickable.
.order-link {
  cursor: pointer;
  color: inherit;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}
</style>
