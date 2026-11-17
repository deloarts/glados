<script setup lang="ts">
// The Manage Quotes panel of one lot: every position a supplier may still
// work is offered as a line of a quote request with its remaining quantity;
// a row can be left out. The award assigns each to the supplier that won it.
import { ref, watch } from 'vue'

import { hasAction } from '@/core/utils/lifecycleActions'
import { QuoteRequestPanel, mergeQuotePanelRows } from '@/features/quote-requests'
import type { QuotePanelRow } from '@/features/quote-requests'
import { MADE_ITEM_ORDER_UNIT } from '../../utils/madeItemOrderUnit'
import { sortedSteps, stepMethodLabel } from '../../utils/lotStepDisplay'
import { bySequence } from '../../utils/sequence'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ lotId: number }>()

const detailStore = useProductionLotDetailStore()
const rows = ref<QuotePanelRow[]>([])

function buildRows(): QuotePanelRow[] {
  const lot = detailStore.lot
  if (!lot) return []
  return [...lot.positions]
    .filter((p) => hasAction(p, 'assign_external'))
    .sort(bySequence)
    .map((position) => ({
      key: `${lot.id}:${position.id}`,
      title: `${lot.lot_number} #${position.sequence}`,
      subtitle: sortedSteps(position)
        .map((step) => stepMethodLabel(step))
        .join(', '),
      projectNumber: '',
      unit: MADE_ITEM_ORDER_UNIT,
      quantity: position.quantity_remaining,
      quantityEdited: false,
      maxQuantity: position.quantity_remaining,
      shares: [],
      identity: { lot_position_id: position.id },
    }))
}

watch(
  () => detailStore.lot,
  () => {
    rows.value = mergeQuotePanelRows(rows.value, buildRows())
  },
  { immediate: true },
)

async function onAdded(): Promise<void> {
  await detailStore.fetch(props.lotId)
  rows.value = buildRows()
}
</script>

<template>
  <QuoteRequestPanel
    v-bind="$attrs"
    v-model:rows="rows"
    help-slug="production/manage-quotes"
    :selected-count="rows.length"
    removable-rows
    @added="onAdded"
    @clear="rows = []"
  />
</template>
