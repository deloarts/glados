<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDateOrDash, formatDateTimeOrEmpty } from '@/core/utils/dates'
import { getOrders } from '../api/getOrders'
import { useOrderFormatters } from '../composables/useOrderFormatters'

import type { OrderItemResponse } from '../types/ordersResponse'
import type { OrderResponse } from '../types/ordersResponse'
import { formatUnit } from '@/shared/utils/units'
import type { BoughtItemResponse } from '@/features/bought-items'

const props = defineProps<{
  item: BoughtItemResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

/** The dialog has no paginator and shows at most this many orders. */
const ORDER_HISTORY_LIMIT = 200

const { t } = useI18n()
const { formatPositionPrice, orderStatusSeverity, orderItemStatusSeverity } = useOrderFormatters()

const loading = ref(false)
const orders = ref<OrderResponse[]>([])

interface FlatRow {
  order: OrderResponse
  orderItem: OrderItemResponse
}

const rows = computed<FlatRow[]>(() => {
  if (!props.item) return []
  return orders.value.flatMap((order) =>
    (order.items ?? [])
      .filter((i) => i.bought_item_id === props.item!.id)
      .map((orderItem) => ({ order, orderItem })),
  )
})

watch(visible, async (open) => {
  if (!open || !props.item) return
  loading.value = true
  try {
    const result = await getOrders({ bought_item_id: props.item.id, limit: ORDER_HISTORY_LIMIT })
    orders.value = result.items
  } finally {
    loading.value = false
  }
})

watch(
  () => props.item,
  () => {
    orders.value = []
  },
)
</script>

<template>
  <Dialog
    v-model:visible="visible"
    :header="
      item
        ? `${t('boughtItems.catalogue.orderHistory.title')}, ${item.article_name}`
        : t('boughtItems.catalogue.orderHistory.title')
    "
    modal
    :style="{ width: 'var(--dialog-width-full)' }"
    :draggable="false"
  >
    <div v-if="loading" class="loading-state">
      <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
    </div>
    <div v-else-if="rows.length === 0" class="empty-note">
      {{ t('boughtItems.catalogue.orderHistory.empty') }}
    </div>
    <table v-else class="history-table">
      <thead>
        <tr>
          <th>{{ t('boughtItems.catalogue.orderHistory.columns.orderNumber') }}</th>
          <th>{{ t('boughtItems.catalogue.orderHistory.columns.supplier') }}</th>
          <th>{{ t('boughtItems.catalogue.orderHistory.columns.orderStatus') }}</th>
          <th>{{ t('boughtItems.catalogue.orderHistory.columns.quantity') }}</th>
          <th>{{ t('boughtItems.catalogue.orderHistory.columns.itemStatus') }}</th>
          <th>{{ t('boughtItems.catalogue.orderHistory.columns.orderedDate') }}</th>
          <th>{{ t('boughtItems.catalogue.orderHistory.columns.deliveryDate') }}</th>
          <th>{{ t('boughtItems.catalogue.orderHistory.columns.price') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.orderItem.id"
          :class="{ 'row-delivered': row.orderItem.status === 'delivered' }"
        >
          <td>
            <strong>{{ row.order.order_number }}</strong>
          </td>
          <td>{{ row.order.supplier_name }}</td>
          <td>
            <Tag
              :value="t(`orders.status.${row.order.status}`)"
              :severity="orderStatusSeverity(row.order.status)"
            />
          </td>
          <td class="num-cell">
            {{ row.orderItem.quantity }} {{ formatUnit(row.orderItem.unit) }}
          </td>
          <td>
            <Tag
              :value="t(`orders.items.status.${row.orderItem.status}`)"
              :severity="orderItemStatusSeverity(row.orderItem.status)"
            />
          </td>
          <td :title="formatDateTimeOrEmpty(row.order.ordered_date)">
            {{ formatDateOrDash(row.order.ordered_date) }}
          </td>
          <td :title="formatDateTimeOrEmpty(row.orderItem.delivery_date)">
            {{ formatDateOrDash(row.orderItem.delivery_date) }}
          </td>
          <td class="num-cell">{{ formatPositionPrice(row.orderItem) }}</td>
        </tr>
      </tbody>
    </table>
  </Dialog>
</template>

<style scoped lang="scss">
.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
  font-size: var(--font-size-2xl);
  color: var(--p-text-muted-color);
}

.empty-note {
  padding: var(--space-5) 0;
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);

  th {
    text-align: left;
    padding: var(--space-1) var(--space-3);
    color: var(--p-text-muted-color);
    font-weight: 600;
    font-size: var(--font-size-xs);
    white-space: nowrap;
    border-bottom: 1px solid var(--p-content-border-color);
  }

  td {
    padding: var(--space-2) var(--space-3);
    vertical-align: middle;
    white-space: nowrap;
    border-bottom: 1px solid var(--p-content-border-color);
  }

  .p-dark & td {
    border-bottom-color: var(--p-surface-800);
  }
}

.row-delivered td {
  opacity: 0.6;
}

.num-cell {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
