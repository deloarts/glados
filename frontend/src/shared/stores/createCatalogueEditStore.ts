import { ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * The bulk-edit-panel selection state every catalogue table (source/made/
 * bought items) carries: a toggleable edit mode plus the rows currently
 * selected for it, with selection cleared the moment edit mode turns off.
 */
export function createCatalogueEditStore<TItem>(id: string) {
  return defineStore(id, () => {
    const editMode = ref(false)
    const selectedItems = ref<TItem[]>([])

    function toggleEditMode(): void {
      editMode.value = !editMode.value

      if (!editMode.value) {
        selectedItems.value = []
      }
    }

    function setSelectedItems(items: TItem[]): void {
      selectedItems.value = items
    }

    return {
      editMode,
      selectedItems,

      toggleEditMode,
      setSelectedItems,
    }
  })
}
