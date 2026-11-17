<script setup lang="ts">
// External order section of a lot position's record card: the purchase
// order item the position is bought through, its dates and quantities, the
// earlier lines closed short below it, and the delivery provisions recorded
// against the position.
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import { formatDecimal } from '@/core/utils/numbers'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import type {
  LotPositionProvisionResponse,
  LotPositionResponse,
} from '../../../types/productionLotsResponse'
import type { OrderItemResponse, OrderResponse } from '@/features/orders'

defineProps<{
  position: LotPositionResponse
  provisions: LotPositionProvisionResponse[]
  orderItem: OrderItemResponse | null
  order: OrderResponse | null
}>()

const emit = defineEmits<{
  openOrder: [orderId: number | null]
}>()

const { t } = useI18n()
</script>

<template>
  <div class="sub-section">
    <span class="section-label">{{
      t('production.lots.detail.record.execution.externalOrder')
    }}</span>
    <div v-if="position.order_number" class="order-card">
      <div class="order-card-header">
        <span
          class="field-value field-link"
          role="button"
          tabindex="0"
          @click="emit('openOrder', position.order_id ?? null)"
          @keydown.enter="emit('openOrder', position.order_id ?? null)"
          >{{ position.order_number }}</span
        >
        <span class="field-value">· {{ position.supplier_name }}</span>
        <Tag :value="position.order_item_status" severity="secondary" />
        <Tag
          v-if="position.order_item_closed_short"
          :value="t('production.lots.detail.positions.closedShort')"
          severity="secondary"
        />
      </div>
      <div class="order-dates">
        <span class="field-sublabel">
          {{ t('production.lots.detail.record.orderDetail.orderedBy') }}:
          {{
            orderItem?.orderer?.full_name ??
            orderItem?.creator?.full_name ??
            getEmptyPlaceholder()
          }}
          <template v-if="orderItem?.ordered_date">
            ({{ formatISODateTime(orderItem.ordered_date) }})
          </template>
        </span>
        <span class="field-sublabel">
          {{ t('production.lots.detail.record.orderDetail.plannedDelivery') }}:
          {{
            orderItem?.expected_delivery_date ??
            position.expected_delivery_date ??
            getEmptyPlaceholder()
          }}
        </span>
        <span
          v-if="!orderItem?.expected_delivery_date && position.planned_delivery_date"
          class="field-sublabel"
        >
          {{ t('production.lots.detail.record.orderDetail.plannedDeliveryForecast') }}:
          {{ position.planned_delivery_date }}
        </span>
        <span v-if="orderItem?.expected_pickup_date" class="field-sublabel">
          {{ t('production.lots.detail.record.orderDetail.plannedPickup') }}:
          {{ orderItem.expected_pickup_date }}
        </span>
        <span
          v-if="!orderItem?.expected_pickup_date && position.planned_pickup_date"
          class="field-sublabel"
        >
          {{ t('production.lots.detail.record.orderDetail.plannedPickupForecast') }}:
          {{ position.planned_pickup_date }}
        </span>
        <span v-if="orderItem?.delivery_date" class="field-sublabel">
          {{ t('production.lots.detail.record.orderDetail.delivered') }}:
          {{ formatISODateTime(orderItem.delivery_date) }}
        </span>
        <span v-if="orderItem" class="field-sublabel">
          {{ t('production.lots.detail.record.orderDetail.quantity') }}:
          {{ formatDecimal(orderItem.quantity_delivered) }} /
          {{ formatDecimal(orderItem.quantity) }}
          {{ orderItem.unit }}
          <template v-if="orderItem.items_per_unit !== 1">
            ({{
              t('production.lots.detail.record.orderDetail.itemsPerUnit', {
                count: formatDecimal(orderItem.items_per_unit),
              })
            }})
          </template>
        </span>
        <span v-if="orderItem?.storage_place" class="field-sublabel">
          {{ t('production.lots.detail.record.orderDetail.storagePlace') }}:
          {{ orderItem.storage_place }}
        </span>
        <span v-if="orderItem?.ready_for_pickup_date" class="field-sublabel">
          {{ t('production.lots.detail.record.orderDetail.readyForPickup') }}:
          {{ orderItem.ready_for_pickup_date }}
        </span>
        <span v-if="orderItem?.receiver" class="field-sublabel">
          {{ t('production.lots.detail.record.orderDetail.receivedBy') }}:
          {{ orderItem.receiver.full_name }}
        </span>
        <span v-if="orderItem?.note" class="field-sublabel">
          {{ t('production.lots.detail.record.orderDetail.note') }}: {{ orderItem.note }}
        </span>
        <span v-if="order" class="field-sublabel">
          {{ t('production.lots.detail.record.orderDetail.orderStatus') }}: {{ order.status }}
        </span>
      </div>
    </div>
    <div v-else class="empty-note">
      {{ t('production.lots.detail.record.execution.notOrdered') }}
    </div>

    <!-- The earlier lines of the position, each closed short, below the newest. -->
    <div
      v-for="line in position.earlier_order_lines"
      :key="line.order_item_id"
      class="order-card"
      data-testid="earlier-order-line"
    >
      <div class="order-card-header">
        <span
          class="field-value field-link"
          role="button"
          tabindex="0"
          @click="emit('openOrder', line.order_id)"
          @keydown.enter="emit('openOrder', line.order_id)"
          >{{ line.order_number }}</span
        >
        <span class="field-value">· {{ line.supplier_name }}</span>
        <Tag
          v-if="line.closed_short"
          :value="t('production.lots.detail.positions.closedShort')"
          severity="secondary"
        />
      </div>
      <span class="field-sublabel">
        {{ t('production.lots.detail.record.orderDetail.quantity') }}:
        {{ formatDecimal(line.quantity_delivered) }} / {{ formatDecimal(line.quantity) }}
        {{ line.unit }}
      </span>
    </div>

    <div v-if="provisions.length" class="provisions">
      <div v-for="provision in provisions" :key="provision.id" class="provision-row">
        <i class="mdi mdi-truck-fast-outline" aria-hidden="true" />
        <span class="field-value">{{ formatDecimal(provision.quantity) }}</span>
        <span class="field-sublabel">{{ provision.provision_date }}</span>
        <span class="field-sublabel">{{
          provision.creator?.full_name ?? getEmptyPlaceholder()
        }}</span>
        <span v-if="provision.note" class="field-sublabel">({{ provision.note }})</span>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.sub-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.section-label {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-link {
  cursor: pointer;
  width: fit-content;

  &:hover {
    color: var(--p-primary-color);
    text-decoration: underline;
  }
}

.field-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.empty-note {
  font-style: italic;
}

.provisions {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.provision-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.order-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);

  &:not(:last-child) {
    margin-bottom: var(--space-2);
  }
}

.order-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.order-dates {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
</style>
