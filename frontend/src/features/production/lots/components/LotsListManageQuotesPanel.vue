<script setup lang="ts">
// The Manage Quotes panel of the lots list: the selected positions, those a
// supplier may still work, become lines of a quote request with their
// remaining quantity. The award assigns each to the supplier that won it,
// as Manage Orders does.
import { ref, watch } from 'vue'

import { QuoteRequestPanel, mergeQuotePanelRows } from '@/features/quote-requests'
import type { QuotePanelRow } from '@/features/quote-requests'
import { MADE_ITEM_ORDER_UNIT } from '../../utils/madeItemOrderUnit'
import { useProductionLotsStore } from '../../stores/productionLotsStore'
import { useProductionLotsSelectionStore } from '../stores/productionLotsSelectionStore'
import { sortedSteps, stepMethodLabel } from '../../utils/lotStepDisplay'

defineOptions({ inheritAttrs: false })

const lotsStore = useProductionLotsStore()
const selectionStore = useProductionLotsSelectionStore()

const rows = ref<QuotePanelRow[]>([])

function buildRows(): QuotePanelRow[] {
  return selectionStore.items.map((item) => ({
    key: `${item.lotId}:${item.position.id}`,
    title: `${item.lotNumber} #${item.position.sequence}`,
    subtitle: [
      item.madeItemPartNumber,
      sortedSteps(item.position)
        .map((step) => stepMethodLabel(step))
        .join(', '),
    ]
      .filter(Boolean)
      .join(' · '),
    projectNumber: '',
    unit: MADE_ITEM_ORDER_UNIT,
    quantity: item.position.quantity_remaining,
    quantityEdited: false,
    maxQuantity: item.position.quantity_remaining,
    shares: [],
    identity: { lot_position_id: item.position.id },
  }))
}

watch(
  () => selectionStore.items,
  () => {
    rows.value = mergeQuotePanelRows(rows.value, buildRows())
  },
  { immediate: true, deep: true },
)

function onAdded(): void {
  selectionStore.clearSelection()
  lotsStore.triggerRefresh()
}
</script>

<template>
  <QuoteRequestPanel
    v-bind="$attrs"
    v-model:rows="rows"
    help-slug="production/manage-quotes"
    :selected-count="selectionStore.items.length"
    @added="onAdded"
    @clear="selectionStore.clearSelection()"
  />
</template>
