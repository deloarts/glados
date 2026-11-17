import { computed, type Ref } from 'vue'

import { useRowOpenGuard } from '@/core/composables/useRowOpenGuard'
import { useProductionLotsEditStore } from '../../stores/productionLotsEditStore'

import type { DataTableRowClickEvent, DataTableRowSelectEvent } from 'openvue/datatable'
import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

// Row click and Enter open the lot, except in the Manage and bulk edit modes
// where the row's controls take precedence. A ctrl or shift click and a
// checkbox toggle select rows instead of opening one.
export function useLotsTableRowInteraction(
  showManageOrders: Ref<boolean>,
  showManageProduction: Ref<boolean>,
  showManageSource: Ref<boolean>,
  lotOf: (data: unknown) => LotSummaryResponse,
  emitOpenLot: (lot: LotSummaryResponse) => void,
) {
  const editStore = useProductionLotsEditStore()

  const canOpenRow = computed<boolean>(
    () =>
      !showManageOrders.value &&
      !showManageProduction.value &&
      !showManageSource.value &&
      !editStore.editMode,
  )

  function openLotFromRow(data: unknown): void {
    if (!canOpenRow.value) return
    emitOpenLot(lotOf(data))
  }

  // single selection mode is only bound while no Manage mode owns selection,
  // and selection itself stays unbound, see the OpenVue pitfalls in
  // docs/reference/frontend-conventions.md.
  const { guard: guardRowOpen } = useRowOpenGuard<number>()

  function isModifiedClick(event: Event): boolean {
    const e = event as MouseEvent
    return e.ctrlKey || e.metaKey || e.shiftKey
  }

  function onRowClick(event: DataTableRowClickEvent): void {
    if (isModifiedClick(event.originalEvent)) return
    guardRowOpen(lotOf(event.data).id, () => openLotFromRow(event.data))
  }

  function onRowSelect(event: DataTableRowSelectEvent): void {
    if (event.type === 'checkbox' || isModifiedClick(event.originalEvent)) return
    guardRowOpen(lotOf(event.data).id, () => openLotFromRow(event.data))
  }

  return { canOpenRow, onRowClick, onRowSelect }
}
