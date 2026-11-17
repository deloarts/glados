<script setup lang="ts">
// Read-only card of an order's extra costs and totals beside its lines; the
// costs are edited through the page's controls bar.
import { useI18n } from 'vue-i18n'

import { formatPrice } from '@/core/utils/currency'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import { extraCostName, signedExtraCost } from '@/shared/utils/extraCosts'
import type { OrderResponse } from '../types/ordersResponse'

const props = defineProps<{ order: OrderResponse }>()

const { t } = useI18n()

function lineName(lineId: number | null): string | null {
  if (lineId === null) return null
  const line = props.order.items.find((item) => item.id === lineId)
  return line ? `${line.position}. ${line.item_article_name}` : null
}
</script>

<template>
  <SectionCard :title="t('common.extraCosts.title')" icon="mdi-cash-plus">
    <ul v-if="props.order.extra_costs.length > 0" class="cost-list">
      <li v-for="cost in props.order.extra_costs" :key="cost.id" class="cost-item">
        <span class="cost-name">
          {{ extraCostName(t, cost) }}
          <small v-if="lineName(cost.order_item_id)" class="cost-line">
            {{ lineName(cost.order_item_id) }}
          </small>
        </span>
        <span class="cost-amount">{{ formatPrice(signedExtraCost(cost.kind, cost.amount)) }}</span>
      </li>
    </ul>
    <p v-else class="cost-empty">{{ t('common.extraCosts.none') }}</p>
    <dl class="totals">
      <dt>{{ t('common.extraCosts.linesTotal') }}</dt>
      <dd>{{ formatPrice(props.order.lines_total) }}</dd>
      <dt>{{ t('common.extraCosts.title') }}</dt>
      <dd>{{ formatPrice(props.order.extra_costs_total) }}</dd>
      <dt class="net">{{ t('common.extraCosts.netTotal') }}</dt>
      <dd class="net">{{ formatPrice(props.order.net_total) }}</dd>
    </dl>
  </SectionCard>
</template>

<style scoped lang="scss">
.cost-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.cost-item {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
}

.cost-name {
  display: flex;
  flex-direction: column;
}

.cost-line {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}

.cost-amount {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.cost-empty {
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.totals {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-1) var(--space-3);
  margin: 0;
  padding-top: var(--space-2);
  border-top: 1px solid var(--p-content-border-color);
  font-size: var(--font-size-sm);

  dt {
    color: var(--p-text-muted-color);
  }

  dd {
    margin: 0;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .net {
    font-weight: 600;
    color: var(--p-text-color);
  }
}
</style>
