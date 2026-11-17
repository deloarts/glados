<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import WeekTag from '../WeekTag.vue'

import type { OrderResponse } from '../../types/ordersResponse'

const props = defineProps<{
  order: OrderResponse
  canWrite: boolean
  isSettable: boolean
}>()

const emit = defineEmits<{
  'set-expected-delivery': [order: OrderResponse]
}>()

const { t } = useI18n()
const { missing } = useMissingPermission()
// canWrite is write:orders; without it the button stays visible but disabled.
const writeBlocked = computed(() => (props.canWrite ? '' : missing(Permission.WRITE_ORDERS)))
</script>

<template>
  <div class="date-cell">
    <template v-if="order.expected_delivery_date">
      <span>{{ order.expected_delivery_date }}</span>
      <WeekTag :date="order.expected_delivery_date" />
    </template>
    <template v-else>
      <span v-if="isSettable" v-tooltip.top="writeBlocked || undefined">
        <Button
          :label="t('orders.actions.setExpectedDelivery')"
          size="small"
          text
          :disabled="!canWrite"
          data-testid="order-set-expected-delivery"
          @click="emit('set-expected-delivery', order)"
          style="margin-left: -0.5rem"
        />
      </span>
      <span v-else>{{ getEmptyPlaceholder() }}</span>
    </template>
  </div>
</template>

<style scoped lang="scss">
.date-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  white-space: nowrap;
}
</style>
