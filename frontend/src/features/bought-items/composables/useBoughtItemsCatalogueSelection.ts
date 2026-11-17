import { useRouter } from 'vue-router'

import { useCatalogueRowSelection } from '@/shared/composables/useCatalogueRowSelection'
import { useBoughtItemsCatalogueEditStore } from '../stores/boughtItemsCatalogueEditStore'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'

// Bulk edit checkboxes and row click navigation share one DataTable, see
// useCatalogueRowSelection for how the two gestures stay apart.
export function useBoughtItemsCatalogueSelection(canSelect: () => boolean) {
  const router = useRouter()
  const editStore = useBoughtItemsCatalogueEditStore()

  function navigateToDetail(item: BoughtItemResponse): void {
    void router.push(`/catalogue/bought-items/${item.id}`)
  }

  return {
    ...useCatalogueRowSelection<BoughtItemResponse>({
      editStore,
      canSelect,
      openDetail: navigateToDetail,
    }),
    navigateToDetail,
  }
}
