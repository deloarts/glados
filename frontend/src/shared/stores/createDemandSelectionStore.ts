import { ref } from 'vue'
import type { Ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * Builds the selection store of a demands table: the rows the bulk checkbox
 * column and the Manage panels work on, and a counter other components bump
 * to make the table refetch. The bought, made and source item demand tables
 * each get one under their own store id, so their selections stay apart.
 */
export function createDemandSelectionStore<T>(id: string) {
  return defineStore(id, () => {
    const selectedDemands = ref([]) as Ref<T[]>
    const refreshTrigger = ref(0)

    function clearSelection(): void {
      selectedDemands.value = []
    }

    function triggerRefresh(): void {
      refreshTrigger.value++
    }

    return {
      selectedDemands,
      refreshTrigger,
      clearSelection,
      triggerRefresh,
    }
  })
}
