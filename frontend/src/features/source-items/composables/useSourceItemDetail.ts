import { ref } from 'vue'

import { sourceItemsApi } from '../api/sourceItemsApi'
import type { SourceItemResponse } from '../types/sourceItemsResponse'

/**
 * Opens the source-item detail dialog from a row that only carries an id.
 * Mirrors useBoughtItemDetail/useMadeItemDetail; source items have no
 * dedicated get-by-id endpoint, so the list endpoint is filtered down to the
 * single row instead.
 */
export function useSourceItemDetail() {
  const detailItem = ref<SourceItemResponse | null>(null)
  const showDetail = ref(false)

  async function openDetailById(id: number): Promise<void> {
    detailItem.value = null
    showDetail.value = true
    const page = await sourceItemsApi.list({ id, limit: 1 })
    detailItem.value = page.items[0] ?? null
  }

  return { detailItem, showDetail, openDetailById }
}
