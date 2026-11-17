<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { OrderItemResponse } from '../../types/ordersResponse'

defineProps<{ item: OrderItemResponse }>()

const { t } = useI18n()
</script>

<template>
  <div class="item-cell">
    <span class="item-name">{{ item.item_article_name }}</span>
    <Tag :value="t('orders.items.virtualBadge')" severity="warn" class="virtual-badge" />
    <template v-if="item.demand_substitutions?.length">
      <div
        v-for="sub in item.demand_substitutions"
        :key="sub.demand_item_id"
        class="subst-for"
        v-tooltip="
          sub.substitute_reason
            ? `${t('orders.items.substituteFor')}: ${sub.original_item_article_name} - ${sub.original_item_order_code_1}\n${t('orders.items.substituteReason')}: ${sub.substitute_reason}`
            : `${t('orders.items.substituteFor')}: ${sub.original_item_article_name} - ${sub.original_item_order_code_1}`
        "
      >
        <i class="mdi mdi-swap-horizontal subst-for-icon" aria-hidden="true" />
        <span class="subst-for-label"
          >{{ sub.original_item_article_name }} - {{ sub.original_item_order_code_1 }}</span
        >
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 10rem;
}

.item-name {
  font-weight: 600;
}

.virtual-badge {
  width: fit-content;
  margin: var(--space-1) 0;
}

.subst-for {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-1);
  cursor: default;
}

.subst-for-icon {
  font-size: var(--font-size-xs);
  color: var(--p-orange-500);
  flex-shrink: 0;
}

.subst-for-label {
  font-size: var(--font-size-xs);
  color: var(--p-orange-500);
  font-style: italic;
}
</style>
