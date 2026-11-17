import { ref } from 'vue'

import { getBoughtItems } from '../api/getBoughtItems'
import { useBoughtItemsStore } from '../stores/boughtItemsStore'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'

// The popover a successor tag opens, previewing the item it points to,
// read from the list store's cache first, falling back to a single-item
// fetch when the successor isn't already loaded on this page.
export function useBoughtItemsCatalogueSuccessorPopover() {
  const boughtItemsStore = useBoughtItemsStore()

  const successorPopover = ref()
  const successorPopoverItem = ref<BoughtItemResponse | null>(null)
  const successorPopoverLoading = ref(false)

  async function onSuccessorTagClick(event: Event, id: number): Promise<void> {
    successorPopoverItem.value = null
    successorPopoverLoading.value = true
    successorPopover.value.show(event)

    const cached = boughtItemsStore.getById(id)
    if (cached) {
      successorPopoverItem.value = cached
      successorPopoverLoading.value = false
      return
    }

    const result = await getBoughtItems({ id, limit: 1 })
    successorPopoverItem.value = result.items[0] ?? null
    successorPopoverLoading.value = false
  }

  return { successorPopover, successorPopoverItem, successorPopoverLoading, onSuccessorTagClick }
}
