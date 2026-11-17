import { ref } from 'vue'

import { useRowOpenGuard } from '@/core/composables/useRowOpenGuard'

import type { DataTableRowClickEvent, DataTableRowSelectEvent } from 'openvue/datatable'
import type { OrderResponse } from '../types/ordersResponse'

// Expanded-row state and its handlers. selectionMode="single" without a
// bound selection emits both row-click and row-select for one click, so
// useRowOpenGuard keeps a row from toggling open and closed again.
export function useOrdersTableRowExpansion() {
  const expandedRows = ref<Record<string, boolean>>({})

  function toggleRowExpanded(order: OrderResponse): void {
    const id = String(order.id)
    if (expandedRows.value[id]) {
      const next = { ...expandedRows.value }
      delete next[id]
      expandedRows.value = next
    } else {
      expandedRows.value = { ...expandedRows.value, [id]: true }
    }
  }

  const { guard: guardRowOpen } = useRowOpenGuard<number>()

  function onRowClick(event: DataTableRowClickEvent): void {
    const order = event.data
    guardRowOpen(order.id, () => toggleRowExpanded(order))
  }

  function onRowSelect(event: DataTableRowSelectEvent): void {
    const order = event.data
    guardRowOpen(order.id, () => toggleRowExpanded(order))
  }

  return { expandedRows, toggleRowExpanded, onRowClick, onRowSelect }
}
