<script setup lang="ts">
// The Manage Quotes panel of the source item demands: the selected demands,
// grouped per material, unit and project like Manage Orders, become lines
// of a quote request, each demand with its open quantity as its share.
import { ref, watch } from 'vue'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { QuoteRequestPanel, mergeQuotePanelRows } from '@/features/quote-requests'
import type { QuotePanelRow } from '@/features/quote-requests'
import { useSourceItemDemandsSelectionStore } from '../stores/sourceItemDemandsSelectionStore'
import { useSourceItemsAllocationsStore } from '../stores/sourceItemsAllocationsStore'
import type { SourceItemDemandResponse } from '@/features/source-items'
import { localizeLabel } from '@/shared/utils/localizeLabel'

defineOptions({ inheritAttrs: false })

const selectionStore = useSourceItemDemandsSelectionStore()
const allocationsStore = useSourceItemsAllocationsStore()

const rows = ref<QuotePanelRow[]>([])

function itemLabel(d: SourceItemDemandResponse): string {
  if (d.bought_item) return d.bought_item.article_name
  if (d.source_item) return d.source_item.dimension || `Source item #${d.source_item.id}`
  return getEmptyPlaceholder()
}

function itemCode(d: SourceItemDemandResponse): string {
  if (d.bought_item) return d.bought_item.order_code_1
  if (d.source_item) {
    return (
      [d.source_item.order_code_1, d.source_item.order_code_2].filter(Boolean).join(' | ') ||
      [d.source_item.material, localizeLabel(d.source_item.type_name)].filter(Boolean).join(' | ')
    )
  }
  return ''
}

function buildRows(): QuotePanelRow[] {
  const grouped = new Map<string, QuotePanelRow>()
  for (const d of selectionStore.selectedDemands) {
    const material =
      d.bought_item_id !== null ? `bought:${d.bought_item_id}` : `source:${d.source_item_id}`
    const key = `${material}|${d.unit}|${d.project_id}`
    const share = {
      family: 'source' as const,
      demandId: d.id,
      quantity: allocationsStore.getSummary(d.id)?.unallocated ?? d.quantity,
    }
    const existing = grouped.get(key)
    if (existing) {
      existing.shares.push(share)
      continue
    }
    grouped.set(key, {
      key,
      title: itemLabel(d),
      subtitle: itemCode(d),
      projectNumber: d.project_number,
      unit: d.unit,
      quantity: 0,
      quantityEdited: false,
      shares: [share],
      identity:
        d.bought_item_id !== null
          ? { bought_item_id: d.bought_item_id, project_id: d.project_id }
          : { source_item_id: d.source_item_id, project_id: d.project_id },
    })
  }
  return [...grouped.values()]
}

watch(
  () => selectionStore.selectedDemands,
  () => {
    rows.value = mergeQuotePanelRows(rows.value, buildRows())
  },
  { immediate: true },
)

function onAdded(): void {
  selectionStore.clearSelection()
  selectionStore.triggerRefresh()
}
</script>

<template>
  <QuoteRequestPanel
    v-bind="$attrs"
    v-model:rows="rows"
    :selected-count="selectionStore.selectedDemands.length"
    @added="onAdded"
    @clear="selectionStore.clearSelection()"
  />
</template>
