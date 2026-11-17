<script setup lang="ts">
// The Item cell of the bought item demands table: the item's name, which
// opens the item, its order code, and the substitutes the demand's
// allocations use, each with its reason as tooltip.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useBoughtItemsAllocationsStore } from '../stores/boughtItemsAllocationsStore'
import type { BoughtItemDemandResponse } from '@/features/bought-items'


const props = defineProps<{
  demand: BoughtItemDemandResponse
}>()

const emit = defineEmits<{
  openItem: [itemId: number]
}>()

const { t } = useI18n()
const allocationsStore = useBoughtItemsAllocationsStore()

const substitutions = computed(
  () => allocationsStore.getSummary(props.demand.id)?.substitutions ?? [],
)
</script>

<template>
  <div class="item-cell">
    <span
      class="item-name item-link"
      role="button"
      tabindex="0"
      @click.stop="emit('openItem', demand.item_id)"
      @keydown.enter="emit('openItem', demand.item_id)"
      >{{ demand.item_article_name }}</span
    >
    <span class="item-code">{{ demand.item_order_code_1 }}</span>
    <div
      v-for="sub in substitutions"
      :key="sub.substitute_item_id"
      class="subst-info"
      v-tooltip="
        sub.substitute_reason
          ? `${t('boughtItems.demands.substitution.reason')}: ${sub.substitute_reason}`
          : t('boughtItems.demands.substitution.tooltip')
      "
    >
      <i class="mdi mdi-swap-horizontal subst-icon" aria-hidden="true" />
      <span class="subst-label">
        {{ sub.substitute_item_article_name }} - {{ sub.substitute_item_order_code_1 }}
      </span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.item-link {
  cursor: pointer;
  color: inherit;
  width: fit-content;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.item-name {
  font-size: var(--font-size-md);
  font-weight: 600;
}

.item-code {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.subst-info {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-1);
  cursor: default;
}

.subst-icon {
  padding-right: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--p-primary-color);
  flex-shrink: 0;
}

.subst-label {
  font-size: var(--font-size-xs);
  color: var(--p-primary-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
