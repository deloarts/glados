<script setup lang="ts">
// The Manage Quotes panel of the bought item demands: the selected demands,
// grouped per item, unit and project like Manage Orders, become lines of a
// quote request, each demand with its open quantity as its share. The
// suppliers the items were ordered from before are suggested first.
import { ref, watch } from 'vue'

import { getOrders } from '@/features/orders'
import { QuoteRequestPanel, mergeQuotePanelRows } from '@/features/quote-requests'
import type { QuotePanelRow } from '@/features/quote-requests'
import { useBoughtItemsProcurementStore } from '../stores/boughtItemsProcurementStore'
import { useBoughtItemsAllocationsStore } from '../stores/boughtItemsAllocationsStore'

defineOptions({ inheritAttrs: false })

const procurementStore = useBoughtItemsProcurementStore()
const allocationsStore = useBoughtItemsAllocationsStore()

const rows = ref<QuotePanelRow[]>([])
const suggestedSupplierIds = ref<number[]>([])

function buildRows(): QuotePanelRow[] {
  const grouped = new Map<string, QuotePanelRow>()
  for (const d of procurementStore.selectedDemands) {
    const key = `${d.item_id}|${d.unit}|${d.project_id}`
    const share = {
      family: 'bought' as const,
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
      title: d.item_article_name,
      subtitle: d.item_order_code_1,
      projectNumber: d.project_number,
      unit: d.unit,
      quantity: 0,
      quantityEdited: false,
      shares: [share],
      identity: { bought_item_id: d.item_id, project_id: d.project_id },
    })
  }
  return [...grouped.values()]
}

async function suggestSuppliers(): Promise<void> {
  const itemIds = [...new Set(procurementStore.selectedDemands.map((d) => d.item_id))].slice(0, 5)
  const seen = new Set<number>()
  for (const itemId of itemIds) {
    try {
      const page = await getOrders({ bought_item_id: itemId, limit: 20 })
      for (const order of page.items) seen.add(order.supplier_id)
    } catch {
      // A suggestion is optional.
    }
  }
  suggestedSupplierIds.value = [...seen]
}

watch(
  () => procurementStore.selectedDemands,
  () => {
    rows.value = mergeQuotePanelRows(rows.value, buildRows())
    void suggestSuppliers()
  },
  { immediate: true },
)

function onAdded(): void {
  procurementStore.clearSelection()
  procurementStore.triggerRefresh()
}
</script>

<template>
  <QuoteRequestPanel
    v-bind="$attrs"
    v-model:rows="rows"
    :selected-count="procurementStore.selectedDemands.length"
    :suggested-supplier-ids="suggestedSupplierIds"
    @added="onAdded"
    @clear="procurementStore.clearSelection()"
  />
</template>
