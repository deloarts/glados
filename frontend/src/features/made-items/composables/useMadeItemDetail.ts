import { ref } from 'vue'

import { getMadeItems } from '../api/getMadeItems'
import type { MadeItemResponse } from '../types/madeItemsResponse'

export function useMadeItemDetail() {
  const detailItem = ref<MadeItemResponse | null>(null)
  const showDetail = ref(false)

  async function openDetailById(id: number): Promise<void> {
    detailItem.value = null
    showDetail.value = true
    const page = await getMadeItems({ id, limit: 1 })
    detailItem.value = page.items[0] ?? null
  }

  return { detailItem, showDetail, openDetailById }
}
