import { computed, ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { MenuItem } from 'openvue/menuitem'

/** The part of the items table the views bar reads and resets. */
interface ItemsTableFilters {
  hasActiveFilters: boolean
  clearFilters: () => void
}

/**
 * The views bar state of the order page: grouping and sorting of the lines.
 * Local, since nothing here needs to survive navigation. Column row filters
 * live inside OrderItemsTable, which reports whether any is set through its
 * exposed hasActiveFilters, and the Clear button resets them through the
 * exposed clearFilters().
 */
export function useOrderDetailViews(itemsTable: Ref<ItemsTableFilters | null>) {
  const { t } = useI18n()

  const groupBy = ref<'status' | 'project' | null>(null)
  const sortField = ref<string | undefined>(undefined)
  const sortOrder = ref<number | undefined>(undefined)

  const groupByItems = computed<MenuItem[]>(() => [
    {
      label: t('orders.views.groupByItems.status'),
      icon: 'mdi mdi-flag-outline',
      command: () => {
        groupBy.value = 'status'
      },
    },
    {
      label: t('orders.items.columns.project'),
      icon: 'mdi mdi-folder-outline',
      command: () => {
        groupBy.value = 'project'
      },
    },
  ])

  function setSort(field: string, order: 1 | -1): void {
    sortField.value = field
    sortOrder.value = order
  }

  function clearSort(): void {
    sortField.value = undefined
    sortOrder.value = undefined
  }

  const sortByItems = computed<MenuItem[]>(() => [
    {
      label: t('orders.items.views.sortByItems.positionAsc'),
      icon: 'mdi mdi-sort-numeric-ascending',
      command: () => setSort('position', 1),
    },
    {
      label: t('orders.items.views.sortByItems.positionDesc'),
      icon: 'mdi mdi-sort-numeric-descending',
      command: () => setSort('position', -1),
    },
    {
      label: t('orders.items.views.sortByItems.statusAsc'),
      icon: 'mdi mdi-sort-alphabetical-ascending',
      command: () => setSort('status', 1),
    },
    {
      label: t('orders.items.views.sortByItems.statusDesc'),
      icon: 'mdi mdi-sort-alphabetical-descending',
      command: () => setSort('status', -1),
    },
    {
      label: t('orders.items.views.sortByItems.expectedDeliveryDesc'),
      icon: 'mdi mdi-sort-clock-descending',
      command: () => setSort('expected_delivery_date', -1),
    },
    {
      label: t('orders.items.views.sortByItems.expectedDeliveryAsc'),
      icon: 'mdi mdi-sort-clock-ascending',
      command: () => setSort('expected_delivery_date', 1),
    },
    {
      label: t('orders.items.views.sortByItems.priceDesc'),
      icon: 'mdi mdi-sort-numeric-descending',
      command: () => setSort('price', -1),
    },
    {
      label: t('orders.items.views.sortByItems.priceAsc'),
      icon: 'mdi mdi-sort-numeric-ascending',
      command: () => setSort('price', 1),
    },
  ])

  const hasActiveViewFilters = computed(
    () => !!groupBy.value || !!sortField.value || (itemsTable.value?.hasActiveFilters ?? false),
  )

  function clearViews(): void {
    groupBy.value = null
    clearSort()
    itemsTable.value?.clearFilters()
  }

  return {
    groupBy,
    sortField,
    sortOrder,
    groupByItems,
    sortByItems,
    hasActiveViewFilters,
    clearSort,
    clearViews,
  }
}
