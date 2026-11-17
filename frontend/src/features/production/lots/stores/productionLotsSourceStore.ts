import { ref } from 'vue'
import { defineStore } from 'pinia'

import type { LotSummaryResponse } from '../../types/productionLotsResponse'

// Whole-row lot selection for the Manage Source panel. Deliberately not
// productionLotsSelectionStore (position-shaped, per-lot getLot() fetches;
// source is a lot-level attribute already present on the summary row) nor
// productionLotsEditStore (its editMode flag doubles as bulk-edit's own
// button state and drives the panels' mutual-exclusion watcher).
export const useProductionLotsSourceStore = defineStore('productionLotsSource', () => {
  const selectedLots = ref<LotSummaryResponse[]>([])

  function setSelectedLots(items: LotSummaryResponse[]): void {
    selectedLots.value = items
  }

  function removeLot(lotId: number): void {
    selectedLots.value = selectedLots.value.filter((lot) => lot.id !== lotId)
  }

  function clearSelection(): void {
    selectedLots.value = []
  }

  return {
    selectedLots,

    setSelectedLots,
    removeLot,
    clearSelection,
  }
})
