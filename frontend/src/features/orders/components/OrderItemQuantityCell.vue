<script setup lang="ts">
// Quantity of an order item, with the delivered part and, once pieces were
// rejected, one note that also says how many of them are lost.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { OrderItemResponse } from '../types/ordersResponse'
import { formatUnit } from '@/shared/utils/units'

const props = defineProps<{
  item: OrderItemResponse
}>()

const { t } = useI18n()

const rejectedNote = computed(() => {
  const rejected = props.item.quantity_rejected ?? 0
  const lost = props.item.quantity_rejected_lost ?? 0
  if (rejected <= 0) return null
  return lost > 0
    ? t('orders.items.rejectedLostNote', { n: rejected, lost })
    : t('orders.items.rejectedNote', { n: rejected })
})
</script>

<template>
  <div class="qty-cell">
    <span v-if="item.quantity_delivered > 0" class="num-cell nowrap"
      >{{ item.quantity_delivered }} /
      {{ item.quantity }}
      {{ formatUnit(item.unit) }}</span
    >
    <span v-else class="num-cell nowrap"
      >{{ item.quantity }}
      {{ formatUnit(item.unit) }}</span
    >
    <span v-if="rejectedNote" class="rejected-note" data-testid="rejected-note">{{
      rejectedNote
    }}</span>
  </div>
</template>

<style scoped lang="scss">
.num-cell {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.nowrap {
  white-space: nowrap;
}

.qty-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0;
  line-height: 1.25;
}

.rejected-note {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-red-500);
  white-space: nowrap;
}
</style>
