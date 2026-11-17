<script setup lang="ts">
// Expected pickup date of an order item, marked once the goods are ready
// for pickup.
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import type { OrderItemResponse } from '../types/ordersResponse'

defineProps<{
  item: OrderItemResponse
}>()

const { t } = useI18n()
</script>

<template>
  <div class="pickup-cell">
    <span>{{ item.expected_pickup_date ?? getEmptyPlaceholder() }}</span>
    <i
      v-if="item.ready_for_pickup_date"
      class="mdi mdi-check-circle pickup-ready-icon"
      aria-hidden="true"
      v-tooltip="
        t('orders.items.readyForPickup', {
          date: formatISODateTime(item.ready_for_pickup_date!),
        })
      "
    />
  </div>
</template>

<style scoped lang="scss">
.pickup-cell {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  white-space: nowrap;
}

.pickup-ready-icon {
  color: var(--p-green-500);
  font-size: var(--font-size-sm);
}
</style>
