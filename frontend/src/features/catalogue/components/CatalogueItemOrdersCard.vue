<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatDateOrDash, formatDateTimeOrEmpty } from '@/core/utils/dates'
import { formatDecimal } from '@/core/utils/numbers'
import { useOrderFormatters } from '@/features/orders'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { ItemOrderRow } from '../types/itemDetail'
import { formatUnit } from '@/shared/utils/units'

defineProps<{
  rows: ItemOrderRow[]
  loading: boolean
  error: boolean
  truncated: boolean
  limit: number
}>()

const emit = defineEmits<{ 'open-order': [orderId: number] }>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { formatPositionPrice, orderStatusSeverity, orderItemStatusSeverity } = useOrderFormatters()
</script>

<template>
  <Panel :header="t('catalogue.itemDetail.cards.orders')">
    <div class="card-scroll-body">
      <div v-if="loading && rows.length === 0" class="loading-state">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      </div>
      <div v-else-if="error" class="error-state">
        <i class="mdi mdi-alert-outline" aria-hidden="true" />
        {{ t('catalogue.itemDetail.sectionError') }}
      </div>
      <template v-else>
        <DataTable
          :value="rows"
          size="small"
          :show-gridlines="isTableGridlinesEnabled"
          :striped-rows="isTableStripedEnabled"
        >
          <template #empty>
            <EmptyState :message="t('catalogue.itemDetail.orders.empty')" />
          </template>
          <Column
            :header="t('catalogue.itemDetail.orders.columns.orderNumber')"
            style="width: 8rem"
          >
            <template #body="{ data }">
              <span
                class="order-link"
                role="button"
                tabindex="0"
                @click="emit('open-order', (data as ItemOrderRow).order.id)"
                @keydown.enter="emit('open-order', (data as ItemOrderRow).order.id)"
                >{{ (data as ItemOrderRow).order.order_number }}</span
              >
            </template>
          </Column>
          <Column
            :header="t('catalogue.itemDetail.orders.columns.supplier')"
            style="width: 10rem"
          >
            <template #body="{ data }">{{ (data as ItemOrderRow).order.supplier_name }}</template>
          </Column>
          <Column :header="t('catalogue.itemDetail.orders.columns.orderStatus')" style="width: 9rem">
            <template #body="{ data }">
              <Tag
                :value="t(`orders.status.${(data as ItemOrderRow).order.status}`)"
                :severity="orderStatusSeverity((data as ItemOrderRow).order.status)"
              />
            </template>
          </Column>
          <Column :header="t('catalogue.itemDetail.orders.columns.quantity')" style="width: 8rem">
            <template #body="{ data }">
              {{ formatDecimal((data as ItemOrderRow).orderItem.quantity) }}
              {{ formatUnit((data as ItemOrderRow).orderItem.unit) }}
            </template>
          </Column>
          <Column :header="t('catalogue.itemDetail.orders.columns.itemStatus')" style="width: 9rem">
            <template #body="{ data }">
              <Tag
                :value="t(`orders.items.status.${(data as ItemOrderRow).orderItem.status}`)"
                :severity="orderItemStatusSeverity((data as ItemOrderRow).orderItem.status)"
              />
            </template>
          </Column>
          <Column
            :header="t('catalogue.itemDetail.orders.columns.project')"
            style="width: 9rem"
          >
            <template #body="{ data }">{{ (data as ItemOrderRow).orderItem.project_number }}</template>
          </Column>
          <Column
            :header="t('catalogue.itemDetail.orders.columns.orderedDate')"
            style="width: 9rem"
          >
            <template #body="{ data }">
              <span :title="formatDateTimeOrEmpty((data as ItemOrderRow).order.ordered_date)">
                {{ formatDateOrDash((data as ItemOrderRow).order.ordered_date) }}
              </span>
            </template>
          </Column>
          <Column
            :header="t('catalogue.itemDetail.orders.columns.deliveryDate')"
            style="width: 9rem"
          >
            <template #body="{ data }">
              <span :title="formatDateTimeOrEmpty((data as ItemOrderRow).orderItem.delivery_date)">
                {{ formatDateOrDash((data as ItemOrderRow).orderItem.delivery_date) }}
              </span>
            </template>
          </Column>
          <Column :header="t('catalogue.itemDetail.orders.columns.price')" style="width: 8rem">
            <template #body="{ data }">
              {{ formatPositionPrice((data as ItemOrderRow).orderItem) }}
            </template>
          </Column>
        </DataTable>
        <div v-if="truncated" class="truncated-state">
          {{ t('catalogue.itemDetail.truncated', { limit }) }}
        </div>
      </template>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
  font-size: var(--font-size-2xl);
  color: var(--p-text-muted-color);
}

.error-state {
  padding: var(--space-5) 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.truncated-state {
  padding: var(--space-2) var(--space-1) 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}

.order-link {
  cursor: pointer;
  font-weight: 700;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}
</style>
