import { ref } from 'vue'
import { defineStore } from 'pinia'

import { createCatalogueViewStore } from '@/shared/stores/createCatalogueViewStore'

import type { MadeItemSortBy } from '../types/madeItemsRequest'

export type MadeItemGroupBy = 'article_groups' | null

export const useMadeItemsCatalogueViewStore = createCatalogueViewStore<
  'article_groups',
  MadeItemSortBy
>('madeItemsCatalogueView')

/**
 * "Show all revisions", default off. A separate store, since an extra state
 * parameter on createCatalogueViewStore breaks Pinia's type inference for
 * the other catalogue view stores.
 */
export const useMadeItemsShowAllRevisionsStore = defineStore('madeItemsShowAllRevisions', () => {
  const showAllRevisions = ref(false)

  function toggleShowAllRevisions(): void {
    showAllRevisions.value = !showAllRevisions.value
  }

  return { showAllRevisions, toggleShowAllRevisions }
})
