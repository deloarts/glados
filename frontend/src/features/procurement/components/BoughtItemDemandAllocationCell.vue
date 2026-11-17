<script setup lang="ts">
// The Allocated cell of the bought item demands table: what is allocated or
// fulfilled from stock out of the total, a stock marker, and the open rest or
// a check once nothing is left. Reads the demand's allocation summary. An
// ended demand shows no open rest, since it asks for nothing more.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { isEndedDemandStatus } from '@/core/utils/demandStatus'
import { formatUnit } from '@/shared/utils/units'
import { useBoughtItemsAllocationsStore } from '../stores/boughtItemsAllocationsStore'

const props = defineProps<{
  demandId: number
  status: string
}>()

const { t } = useI18n()
const allocationsStore = useBoughtItemsAllocationsStore()

const summary = computed(() => allocationsStore.getSummary(props.demandId))
const ended = computed(() => isEndedDemandStatus(props.status))
</script>

<template>
  <div v-if="summary" class="alloc-cell">
    <span class="alloc-numbers">
      {{ summary.allocated + summary.fulfilled_from_stock }}
      /
      {{ summary.total }}
      {{ formatUnit(summary.unit) }}
    </span>
    <i
      v-if="summary.fulfilled_from_stock > 0"
      class="mdi mdi-package-variant-closed"
      data-testid="alloc-from-stock"
      v-tooltip="
        `${summary.fulfilled_from_stock} ${formatUnit(summary.unit)} ${t('boughtItems.demands.columns.fulfilledFromStockTooltip')}`
      "
      style="color: var(--p-purple-500); font-size: var(--font-size-md)"
      aria-hidden="true"
    />
    <Tag
      v-if="!ended && summary.unallocated > 0"
      :value="`-${summary.unallocated}`"
      severity="warn"
      class="alloc-tag"
      v-tooltip="t('common.unallocatedTooltip', { quantity: summary.unallocated, unit: formatUnit(summary.unit) })"
    />
    <i
      v-else-if="summary.unallocated <= 0"
      class="mdi mdi-check-circle"
      data-testid="alloc-complete"
      style="color: var(--p-green-500); font-size: var(--font-size-md)"
      aria-hidden="true"
    />
  </div>
  <i
    v-else-if="allocationsStore.loadingSummaries"
    class="mdi mdi-loading mdi-spin muted"
    aria-hidden="true"
  />
  <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
</template>

<style scoped lang="scss">
.alloc-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.alloc-numbers {
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
}

.alloc-tag {
  font-size: var(--font-size-xs);
}

.muted {
  color: var(--p-text-muted-color);
}
</style>
