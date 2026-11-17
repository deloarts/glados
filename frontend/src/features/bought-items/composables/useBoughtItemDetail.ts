import { ref } from 'vue'

import { getBoughtItems } from '../api/getBoughtItems'
import type { BoughtItemResponse } from '../types/boughtItemsResponse'

export function useBoughtItemDetail() {
  const detailItem = ref<BoughtItemResponse | null>(null)
  const showDetail = ref(false)

  async function openDetailById(id: number): Promise<void> {
    detailItem.value = null
    showDetail.value = true
    const page = await getBoughtItems({ id, limit: 1 })
    detailItem.value = page.items[0] ?? null
  }

  return { detailItem, showDetail, openDetailById }
}
