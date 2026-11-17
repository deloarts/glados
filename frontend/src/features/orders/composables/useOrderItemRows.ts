import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { FilterMatchMode } from '@openvue/core/api'

import type { DataTableFilterMeta } from 'openvue/datatable'

import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'
import { RowFilterMatchMode, hasActiveRowFilter } from '@/shared/utils/rowFilterModes'

import type { OrderItemResponse, OrderResponse } from '../types/ordersResponse'

export interface OrderItemRowsProps {
  order: OrderResponse
  search: string
  groupBy: 'status' | 'project' | null
}

// Two filters target values the cells compute: the item cell stacks article
// name, order codes, part number and specification, and the price filter
// takes the currency amount the user reads while the API stores cents.
type OrderItemRow = OrderItemResponse & { _itemText: string; _priceMajor: number | null }

function toRow(item: OrderItemResponse): OrderItemRow {
  return {
    ...item,
    _itemText: [
      item.item_article_name,
      item.virtual_name,
      item.item_order_code_1,
      item.item_order_code_2,
      item.item_part_number,
      item.item_revision,
      item.item_specification,
      item.lot_number,
    ]
      .filter((part) => !!part)
      .join('\n'),
    _priceMajor: item.price === null ? null : item.price / 100,
  }
}

// The whole item list arrives with the order, so these filters run client
// side instead of standing in for a server round-trip.
function emptyFilters(): DataTableFilterMeta {
  return {
    status: { value: null, matchMode: FilterMatchMode.IN },
    quantity: { value: null, matchMode: RowFilterMatchMode.NUMBER_RANGE },
    project_number: { value: null, matchMode: FilterMatchMode.CONTAINS },
    _itemText: { value: null, matchMode: FilterMatchMode.CONTAINS },
    expected_delivery_date: { value: null, matchMode: RowFilterMatchMode.DATE_RANGE },
    expected_pickup_date: { value: null, matchMode: RowFilterMatchMode.DATE_RANGE },
    delivery_date: { value: null, matchMode: RowFilterMatchMode.DATE_RANGE },
    _priceMajor: { value: null, matchMode: RowFilterMatchMode.NUMBER_RANGE },
    note: { value: null, matchMode: FilterMatchMode.CONTAINS },
    storage_place: { value: null, matchMode: FilterMatchMode.CONTAINS },
  }
}

/**
 * Rows of the order items table: the filterable row shape, the column
 * filters, grouping by status or project, and the row classes for delivered,
 * edited and search-matching lines.
 */
export function useOrderItemRows(props: OrderItemRowsProps, isEditing: (id: number) => boolean) {
  const { t } = useI18n()

  const filters = ref<DataTableFilterMeta>(emptyFilters())

  function onFiltersUpdate(next: DataTableFilterMeta): void {
    filters.value = next
  }

  // Lets the detail page enable its Clear button while only a column filter
  // is set.
  const hasActiveFilters = computed(() => hasActiveRowFilter(filters.value))

  function clearFilters(): void {
    filters.value = emptyFilters()
  }

  const statusOptions = computed(() =>
    [...new Set((props.order.items ?? []).map((i) => i.status))].map((s) => ({
      label: t(`orders.items.status.${s}`),
      value: s,
    })),
  )

  // OpenVue's subheader mode needs same-group rows to be contiguous, so the
  // rows get a group label field and are sorted by it.
  const groupedItems = computed(() => {
    const items = (props.order.items ?? []).map(toRow)
    if (!props.groupBy) return items

    if (props.groupBy === 'status') {
      return groupRowsByLabel(items, '_statusGroup', (item) =>
        t(`orders.items.status.${item.status}`),
      )
    }

    return groupRowsByLabel(items, '_projectGroup', (item) => item.project_number)
  })

  const groupRowsBy = computed(() => {
    if (!props.groupBy) return undefined
    return props.groupBy === 'status' ? '_statusGroup' : '_projectGroup'
  })

  function itemMatchesSearch(item: OrderItemResponse): boolean {
    if (!props.search) return false
    const term = props.search.toLowerCase()
    return (
      item.item_article_name.toLowerCase().includes(term) ||
      item.item_order_code_1.toLowerCase().includes(term) ||
      (item.item_order_code_2?.toLowerCase().includes(term) ?? false) ||
      item.item_specification.toLowerCase().includes(term)
    )
  }

  function rowClass(item: OrderItemResponse): string[] {
    const classes: string[] = []
    if (item.status === 'delivered') classes.push('row-delivered')
    if (isEditing(item.id)) classes.push('row-editing')
    if (itemMatchesSearch(item)) classes.push('row-search-match')
    return classes
  }

  return {
    filters,
    onFiltersUpdate,
    hasActiveFilters,
    clearFilters,
    statusOptions,
    groupedItems,
    groupRowsBy,
    rowClass,
  }
}
