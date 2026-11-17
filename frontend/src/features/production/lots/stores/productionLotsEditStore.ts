import { ref } from 'vue'
import { defineStore } from 'pinia'

import type { LotSummaryResponse } from '../../types/productionLotsResponse'

export const useProductionLotsEditStore = defineStore('productionLotsEdit', () => {
  const editMode = ref(false)
  const selectedItems = ref<LotSummaryResponse[]>([])

  function toggleEditMode(): void {
    editMode.value = !editMode.value

    if (!editMode.value) {
      selectedItems.value = []
    }
  }

  function setSelectedItems(items: LotSummaryResponse[]): void {
    selectedItems.value = items
  }

  return {
    editMode,
    selectedItems,

    toggleEditMode,
    setSelectedItems,
  }
})
