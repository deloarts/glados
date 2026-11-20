<script setup lang="ts">
// The info bar of the order page: number, status, supplier, total, delivery
// date, a missing invoice, storage place, the supplier order numbers and the
// quote requests the order came from. Empty until the order has loaded.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDateOrDash, formatDateTimeOrEmpty } from '@/core/utils/dates'
import { useHostStore } from '@/core/host/stores/hostStore'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import { useOrderFormatters } from '../composables/useOrderFormatters'
import { useOrderFilesStore } from '../stores/orderFilesStore'
import type { OrderResponse } from '../types/ordersResponse'

const props = defineProps<{ order: OrderResponse | null }>()

const { t } = useI18n()
const hostStore = useHostStore()
const filesStore = useOrderFilesStore()
const { orderTotalPrice, orderStatusSeverity } = useOrderFormatters()

// A partially delivered order already has a delivery date, so its presence
// decides between expected and actual.
const deliveryLabel = computed(() =>
  props.order?.delivery_date
    ? t('orders.columns.deliveryDate')
    : t('orders.columns.expectedDelivery'),
)
const deliveryValue = computed(() => {
  if (!props.order) return null
  return props.order.delivery_date
    ? formatDateOrDash(props.order.delivery_date)
    : (props.order.expected_delivery_date ?? t('orders.detail.noDeliveryDateSet'))
})
const deliveryTooltip = computed(() =>
  props.order?.delivery_date ? formatDateTimeOrEmpty(props.order.delivery_date) : undefined,
)
const storagePlaceValue = computed(
  () => props.order?.storage_place ?? t('orders.detail.noStoragePlaceSet'),
)
const supplierOrderNumbersValue = computed(() => {
  const numbers = props.order?.supplier_order_numbers ?? []
  return numbers.length > 0 ? numbers.join(', ') : t('orders.detail.noSupplierOrderNumbersSet')
})
// Reads the files the side panel's OrderFilesSection already loaded, so the
// hint costs no request of its own. Only a fully delivered order without a
// single invoice file counts; partial invoicing is not visible from files.
const invoiceMissing = computed(
  () =>
    !!props.order &&
    props.order.status === 'delivered' &&
    hostStore.storageEnabled &&
    !filesStore.getFiles(props.order.id).some((f) => f.category === 'invoice'),
)
</script>

<template>
  <InfoBar>
    <template v-if="order">
      <span class="order-number">{{ order.order_number }}</span>
      <span class="info-sep" />
      <Tag
        :value="t(`orders.status.${order.status}`)"
        :severity="orderStatusSeverity(order.status)"
      />
      <span class="info-sep" />
      <span class="info-muted">{{ order.supplier_name }}</span>
      <ArchivedOptionTag
        v-if="order.supplier_archived"
        :tooltip="t('orders.detail.supplierArchived')"
      />
      <span class="info-sep" />
      <span class="info-muted">{{ orderTotalPrice(order) }}</span>
      <span class="info-sep" />
      <span class="info-field" :title="deliveryTooltip">
        <i class="mdi mdi-truck-outline" aria-hidden="true" v-tooltip.bottom="deliveryLabel" />
        <span class="info-muted">{{ deliveryValue }}</span>
      </span>
      <template v-if="invoiceMissing">
        <span class="info-sep" />
        <span
          class="info-field invoice-missing"
          v-tooltip.bottom="t('orders.detail.invoiceMissingTooltip')"
        >
          <i class="mdi mdi-receipt-text-remove-outline" aria-hidden="true" />
          <span>{{ t('orders.detail.invoiceMissing') }}</span>
        </span>
      </template>
      <span class="info-sep" />
      <span class="info-field">
        <i
          class="mdi mdi-map-marker-outline"
          aria-hidden="true"
          v-tooltip.bottom="t('orders.columns.storagePlace')"
        />
        <span class="info-muted">{{ storagePlaceValue }}</span>
      </span>
      <span class="info-sep" />
      <span class="info-field" data-testid="order-supplier-order-numbers">
        <i
          class="mdi mdi-pound-box-outline"
          aria-hidden="true"
          v-tooltip.bottom="t('orders.columns.supplierOrderNumbers')"
        />
        <span class="info-muted">{{ supplierOrderNumbersValue }}</span>
      </span>
      <template v-if="order.quote_requests.length > 0">
        <span class="info-sep" />
        <span class="info-field">
          <i
            class="mdi mdi-scale-balance"
            aria-hidden="true"
            v-tooltip.bottom="t('orders.detail.quoteRequests')"
          />
          <template v-for="(request, index) in order.quote_requests" :key="request.id">
            <span v-if="index > 0" class="info-muted">,</span>
            <RouterLink class="info-link" :to="`/procurement/quotes/${request.id}`">{{
              request.request_number
            }}</RouterLink>
          </template>
        </span>
      </template>
    </template>
  </InfoBar>
</template>

<style scoped lang="scss">
.order-number {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

// Delivery date and storage place carry an icon label, since they are less
// self-evident than a supplier name or price.
.info-field {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--p-text-muted-color);

  i {
    font-size: var(--font-size-md);
  }
}

.info-link {
  color: var(--p-text-muted-color);
  text-decoration: none;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.invoice-missing {
  color: var(--p-orange-500);
}
</style>
