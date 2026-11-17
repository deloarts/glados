<script setup lang="ts">
import { computed } from 'vue'

import { dateToParam as toDateParam } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { sourceDeliveryInfoFor } from '../../../utils/lotStepDisplay'

import ClickableOrderNumber from './ClickableOrderNumber.vue'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

const props = defineProps<{
  lot: LotSummaryResponse
}>()

const info = computed(() => sourceDeliveryInfoFor(props.lot))
</script>

<template>
  <div v-if="info" class="delivery-cell">
    <span v-if="info.date" :class="{ 'delivery-date--projected': !info.isFinal }">
      {{ toDateParam(info.date) }}
    </span>
    <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
    <ClickableOrderNumber
      v-if="info.orderId !== null && info.orderNumber"
      :order-id="info.orderId"
      :order-number="info.orderNumber"
      class="source-order-line"
    />
  </div>
  <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
</template>

<style scoped lang="scss">
.delivery-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.delivery-date--projected {
  color: var(--p-text-muted-color);
  font-style: italic;
}

// Matches the muted second line used by the other two-line cells
// (.item-code / .source-sublabel).
.source-order-line {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
