<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDateOrDash } from '@/core/utils/dates'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

const props = defineProps<{
  lot: LotSummaryResponse
  hasPastTargetDateConflict: boolean
}>()

const { t } = useI18n()

// Shows the resolved target date the scheduler uses, with a note naming its
// origin. Read-only; editing happens from the row context menu.
const note = computed(() => {
  if (props.lot.target_date_source === 'lot') {
    return t('production.lots.columns.requiredDeliverySource.lot')
  }
  if (props.lot.target_date_source === 'demand' && props.lot.target_date_demand_item_id != null) {
    return t('production.lots.columns.requiredDeliverySource.demand', {
      id: props.lot.target_date_demand_item_id,
    })
  }
  return null
})

const noteTooltip = computed(() => {
  if (props.lot.target_date_source === 'lot') {
    return t('production.lots.columns.requiredDeliverySource.lotTooltip')
  }
  if (props.lot.target_date_source === 'demand' && props.lot.target_date_demand_item_id != null) {
    return t('production.lots.columns.requiredDeliverySource.demandTooltip', {
      id: props.lot.target_date_demand_item_id,
    })
  }
  return undefined
})
</script>

<template>
  <div class="required-delivery-cell">
    <span :class="{ 'required-delivery-date--late': hasPastTargetDateConflict }">
      {{ formatDateOrDash(lot.target_date) }}
    </span>
    <span v-if="note" class="required-delivery-note" v-tooltip.top="noteTooltip">{{ note }}</span>
  </div>
</template>

<style scoped lang="scss">
.required-delivery-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

// The current schedule misses the required delivery date.
.required-delivery-date--late {
  color: var(--p-red-500);
  font-weight: bold;
}

// Matches the muted second line of the other two-line cells.
.required-delivery-note {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
