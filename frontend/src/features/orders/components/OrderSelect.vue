<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { useRemoteOptions } from '@/shared/composables/useRemoteOptions'

import { getOrders } from '../api/getOrders'
import { useOrderFormatters } from '../composables/useOrderFormatters'
import { OPEN_ORDER_STATUSES } from '../utils/openOrderStatuses'

import type { OrderResponse, OrderStatus } from '../types/ordersResponse'

// `anyStatus` searches delivered and canceled orders too, for a manual
// allocation that links a demand to work already done. `statuses` narrows
// the open orders to those a caller's action accepts.
const props = defineProps<{
  exclude?: number | null
  anyStatus?: boolean
  statuses?: readonly OrderStatus[]
}>()

const model = defineModel<OrderResponse | null>({ default: null })

const { t } = useI18n()
const toast = useAppToast()
const { orderStatusSeverity } = useOrderFormatters()

// The newest open orders, or with `anyStatus` the newest of any status, that
// match what the user typed. Typing searches on the server, so an order
// beyond this page is found by its number or supplier rather than by
// scrolling.
const OPTIONS_LIMIT = 50

async function searchOrders(query: string): Promise<OrderResponse[]> {
  try {
    const page = await getOrders({
      status: props.anyStatus ? undefined : [...(props.statuses ?? OPEN_ORDER_STATUSES)],
      search: query || undefined,
      limit: OPTIONS_LIMIT,
    })
    return page.items
  } catch (e: unknown) {
    toast.error(t('orders.select.loadFailed'), extractApiError(e) ?? undefined)
    return items.value
  }
}

const { items, loading, debouncedSearch } = useRemoteOptions(searchOrders)

// The chosen order stays an option while a search shows others, so the
// Select can still label it.
const orders = computed(() => {
  const chosen = model.value
  const listed =
    chosen && !items.value.some((o) => o.id === chosen.id) ? [chosen, ...items.value] : items.value
  return props.exclude != null ? listed.filter((o) => o.id !== props.exclude) : listed
})

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/form-control-has-label -- the caller labels it, aria-labelledby falls through to the Select */
</script>

<template>
  <Select
    v-model="model"
    :options="orders"
    option-label="order_number"
    :loading="loading"
    :filter="true"
    :filter-fields="['order_number', 'supplier_name']"
    :placeholder="t('orders.select.placeholder')"
    show-clear
    @filter="(e) => debouncedSearch(e.value)"
  >
    <template #option="{ option }">
      <div class="order-option">
        <span class="order-number"
          >{{ option.order_number }}
          <Tag
            :value="t(`orders.status.${option.status}`)"
            :severity="orderStatusSeverity(option.status)"
        /></span>
        <span class="order-supplier">{{ option.supplier_name }}</span>
      </div>
    </template>
    <template #value="{ value }">
      <span v-if="value">{{ value.order_number }} - {{ value.supplier_name }}</span>
    </template>
    <template #empty>
      <span>{{ t('orders.select.empty') }}</span>
    </template>
  </Select>
</template>

<style scoped lang="scss">
.order-option {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.order-number {
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.order-supplier {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
