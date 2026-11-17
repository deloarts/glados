import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useServerTable } from '@/core/composables/useServerTable'
import { useKeyedDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useKeyedFilterMetaModel } from '@/shared/composables/useFilterMetaModel'
import { useArticleGroupsStore } from '@/features/article-groups'
import { useProductFamiliesStore } from '@/features/product-families'

import { useBoughtItemsStore } from '../stores/boughtItemsStore'
import { useBoughtItemsCatalogueFiltersStore } from '../stores/boughtItemsCatalogueFiltersStore'
import { useBoughtItemsCatalogueViewStore } from '../stores/boughtItemsCatalogueViewStore'
import { useBoughtItemsCatalogueQuery } from './useBoughtItemsCatalogueQuery'
import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'
import { localizeLabel } from '@/shared/utils/localizeLabel'

// Grouping, server-side filtering and paging, and the date-range model.
// Only filters is bound by the template; the rest feeds fetchParams.
export function useBoughtItemsCatalogueFilters() {
  const boughtItemsStore = useBoughtItemsStore()
  const filtersStore = useBoughtItemsCatalogueFiltersStore()
  const viewStore = useBoughtItemsCatalogueViewStore()
  const articleGroupsStore = useArticleGroupsStore()
  const productFamiliesStore = useProductFamiliesStore()

  const groupedItems = computed(() => {
    const items = boughtItemsStore.items
    if (!viewStore.groupBy) return items

    if (viewStore.groupBy === 'article_groups') {
      return groupRowsByLabel(
        items,
        '_categoryGroup',
        (item) => localizeLabel(item.article_groups?.[0]?.name) || getEmptyPlaceholder(),
      )
    }

    return [...items].sort((a, b) =>
      (a.manufacturer_name ?? '').localeCompare(b.manufacturer_name ?? ''),
    )
  })

  const groupRowsBy = computed(() => {
    if (!viewStore.groupBy) return undefined
    return viewStore.groupBy === 'article_groups' ? '_categoryGroup' : 'manufacturer_name'
  })

  const { filters, dateRangeFilters, search, showArchived, clearTrigger } = storeToRefs(filtersStore)
  const { sortBy, sortDir } = storeToRefs(viewStore)
  const listQuery = useBoughtItemsCatalogueQuery()

  const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage, onFilter } =
    useServerTable({
      fetchParams: ({ first, rows }) => ({
        skip: first,
        limit: rows,
        ...listQuery(),
      }),
      fetch: (params) => boughtItemsStore.refresh(params),
    })

  const { getDateRangeModel, setDateRangeModel } = useKeyedDateRangeFilter(dateRangeFilters, onFilter)
  const { getFilterValue, setFilterValue } = useKeyedFilterMetaModel(filters, onFilter)

  watch(search, resetAndFetchDebounced)
  watch(showArchived, resetAndFetch)
  watch(clearTrigger, resetAndFetch)
  watch(
    () => boughtItemsStore.refreshTrigger,
    () => fetchItems(),
  )
  watch([sortBy, sortDir], resetAndFetch)

  onMounted(() => {
    if (articleGroupsStore.items.length === 0) {
      void articleGroupsStore.refresh()
    }
    if (productFamiliesStore.items.length === 0) {
      void productFamiliesStore.refresh()
    }
  })

  return {
    filters,
    groupedItems,
    groupRowsBy,
    first,
    rows,
    onPage,
    onFilter,
    getDateRangeModel,
    setDateRangeModel,
    getFilterValue,
    setFilterValue,
  }
}
