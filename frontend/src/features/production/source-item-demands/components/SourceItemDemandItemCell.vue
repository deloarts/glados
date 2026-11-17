<script setup lang="ts">
// The Item cell of the source item demands table: the item's label and
// sublabel, and the substitutes the demand's allocations use, each with its
// reason as tooltip.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSourceItemsAllocationsStore } from '../stores/sourceItemsAllocationsStore'
import { itemLabel, itemSublabel } from '@/features/source-items'
import type { SourceItemDemandResponse } from '@/features/source-items'

const props = defineProps<{
  demand: SourceItemDemandResponse
}>()

const { t } = useI18n()
const allocationsStore = useSourceItemsAllocationsStore()

const substitutions = computed(
  () => allocationsStore.getSummary(props.demand.id)?.substitutions ?? [],
)
</script>

<template>
  <div class="item-cell">
    <span class="item-name">{{ itemLabel(demand) }}</span>
    <span class="item-code">{{ itemSublabel(demand) }}</span>
    <div
      v-for="sub in substitutions"
      :key="sub.substitute_source_item_id"
      class="subst-info"
      v-tooltip="
        sub.substitute_reason
          ? `${t('sourceItems.demands.substitution.reason')}: ${sub.substitute_reason}`
          : t('sourceItems.demands.substitution.tooltip')
      "
    >
      <i class="mdi mdi-swap-horizontal subst-icon" aria-hidden="true" />
      <span class="subst-label">
        {{ sub.substitute_item_article_name }} -
        {{ sub.substitute_item_order_code_1 || sub.substitute_item_specification }}
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

.item-name {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.item-code {
  font-size: var(--font-size-sm);
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
