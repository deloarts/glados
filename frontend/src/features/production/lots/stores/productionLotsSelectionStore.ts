import { ref } from 'vue'
import { defineStore } from 'pinia'

import { hasAction } from '@/core/utils/lifecycleActions'
import { getLot } from '../../api/getLot'

import type { LotPositionResponse, LotResponse } from '../../types/productionLotsResponse'
import type { OrderResponse } from '@/features/orders'
import type { ProductionMachineResponse } from '@/features/production-machines'
import type { MachinePoolResponse } from '@/features/production-machines'

export type ToggleStepResult = 'added' | 'removed' | 'unavailable'

export interface SelectedItem {
  lotId: number
  lotNumber: string
  projectId: number
  madeItemPartNumber: string
  position: LotPositionResponse
}

export type SelectionMode = 'orders' | 'machines'

// Manage Orders can start or top up the external share of a position that
// offers an external assignment. Manage Production can start or top up the
// internal share of a position that offers an internal assignment, or fill in
// a machine on a queued machine-less order.
function isPositionActionable(position: LotPositionResponse, mode: SelectionMode): boolean {
  if (mode === 'orders') return hasAction(position, 'assign_external')
  if (hasAction(position, 'assign_internal')) return true
  return (position.production_orders ?? []).some((o) =>
    (o.conflicts ?? []).includes('no_machine_assigned'),
  )
}

function itemKey(lotId: number, positionId: number): string {
  return `${lotId}:${positionId}`
}

// Cross-lot batch selection for the Manage Orders and Manage Production panels.
// Keeps its own lot cache, since the detail store tracks only one lot.
export const useProductionLotsSelectionStore = defineStore('productionLotsSelection', () => {
  const selectedOrder = ref<OrderResponse | null>(null)
  const selectedMachine = ref<ProductionMachineResponse | null>(null)
  // Mutually exclusive with selectedMachine; the panel clears the other.
  const selectedPool = ref<MachinePoolResponse | null>(null)
  const items = ref<SelectedItem[]>([])
  const resolvingKeys = ref<Set<string>>(new Set())

  const lotCache = new Map<number, LotResponse>()

  async function fetchLot(lotId: number): Promise<LotResponse> {
    const cached = lotCache.get(lotId)
    if (cached) return cached
    const lot = await getLot(lotId)
    lotCache.set(lotId, lot)
    return lot
  }

  function findItem(lotId: number, positionId: number): SelectedItem | undefined {
    return items.value.find((i) => i.lotId === lotId && i.position.id === positionId)
  }

  function removeItem(lotId: number, positionId: number): void {
    items.value = items.value.filter((i) => !(i.lotId === lotId && i.position.id === positionId))
  }

  async function toggleStep(
    lotId: number,
    positionId: number,
    mode: SelectionMode,
    isCapable?: (position: LotPositionResponse) => boolean,
  ): Promise<ToggleStepResult> {
    if (findItem(lotId, positionId)) {
      removeItem(lotId, positionId)
      return 'removed'
    }

    const key = itemKey(lotId, positionId)
    resolvingKeys.value = new Set(resolvingKeys.value).add(key)

    try {
      const lot = await fetchLot(lotId)
      const position = (lot.positions ?? []).find((p) => p.id === positionId) ?? null

      if (!position || !isPositionActionable(position, mode)) return 'unavailable'
      if (isCapable && !isCapable(position)) return 'unavailable'

      items.value = [
        ...items.value,
        {
          lotId,
          lotNumber: lot.lot_number,
          projectId: lot.project_id,
          madeItemPartNumber: lot.made_item_part_number,
          position,
        },
      ]
      return 'added'
    } catch {
      // Resolved rather than rejected, since the click handler has no try/catch;
      // the user sees the unavailable toast and can retry.
      return 'unavailable'
    } finally {
      const next = new Set(resolvingKeys.value)
      next.delete(key)
      resolvingKeys.value = next
    }
  }

  function clearItems(): void {
    items.value = []
  }

  function clearSelection(): void {
    selectedOrder.value = null
    selectedMachine.value = null
    selectedPool.value = null
    items.value = []
    resolvingKeys.value = new Set()
    lotCache.clear()
  }

  return {
    selectedOrder,
    selectedMachine,
    selectedPool,
    items,
    resolvingKeys,
    toggleStep,
    removeItem,
    clearItems,
    clearSelection,
  }
})
