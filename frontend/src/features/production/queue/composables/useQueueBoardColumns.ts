import { computed, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { useMachineCapability } from '../../composables/useMachineCapability'
import { stepMethodLabel } from '../../utils/lotStepDisplay'
import { orderColumnKey, poolColumnKey } from '../../utils/queueColumnRouting'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'
import type {
  LotPositionResponse,
  LotResponse,
  LotStepResponse,
} from '../../types/productionLotsResponse'
import type { FabricationMethodResponse } from '@/features/fabrication-methods'
import type { MachinePoolResponse } from '@/features/production-machines'

export interface BoardColumn {
  key: string
  kind: 'unassigned' | 'manual' | 'inspection' | 'machine' | 'pool'
  id: number | null
  internal_name: string
  vendor: string
  model: string
  // Member machine count, pool columns only, shown instead of vendor/model.
  poolMachineCount: number | null
  capabilities: FabricationMethodResponse[]
}

// The part of a column the drag handlers need, so callers can pass a
// minimal literal instead of a full BoardColumn.
export interface QueueColumnTarget {
  key: string
  kind: BoardColumn['kind']
  id: number | null
}

/**
 * Columns of the production queue board and the lookups that place an order
 * in one of them.
 */
export function useQueueBoardColumns(lotsById: Ref<Map<number, LotResponse>>) {
  const { t } = useI18n()
  const store = useProductionQueueStore()
  const { getPoolCapability } = useMachineCapability()

  // A pool's capability is the intersection of its members' methods, so
  // every id in it can be resolved to a full method from any member.
  function poolCapabilityMethods(pool: MachinePoolResponse): FabricationMethodResponse[] {
    const ids = getPoolCapability(pool)
    const byId = new Map<number, FabricationMethodResponse>()
    for (const machine of pool.machines) {
      for (const method of machine.fabrication_methods) {
        if (ids.has(method.id) && !byId.has(method.id)) byId.set(method.id, method)
      }
    }
    return [...byId.values()]
  }

  function positionFor(order: ProductionOrderResponse): LotPositionResponse | undefined {
    return lotsById.value.get(order.lot_id)?.positions?.find((p) => p.id === order.lot_position_id)
  }

  function stepsFor(order: ProductionOrderResponse): LotStepResponse[] {
    return positionFor(order)?.steps ?? []
  }

  function processMethodLabel(order: ProductionOrderResponse): string | null {
    const steps = stepsFor(order)
    if (steps.length === 0) return null
    return [...new Set(steps.map((s) => stepMethodLabel(s)))].join(', ')
  }

  function orderColumnKeyFor(order: ProductionOrderResponse): string {
    return orderColumnKey(order, stepsFor(order))
  }

  // The "no machine assigned" column only exists while a truly machine-less,
  // pool-less, non-manual, non-inspection order does; pool-first planning
  // leaves it empty most of the time.
  const hasUnassignedOrders = computed(() =>
    store.orders.some((order) => orderColumnKeyFor(order) === 'unassigned'),
  )

  function syntheticColumn(kind: 'unassigned' | 'manual' | 'inspection', name: string): BoardColumn {
    return {
      key: kind,
      kind,
      id: null,
      internal_name: name,
      vendor: '',
      model: '',
      poolMachineCount: null,
      capabilities: [],
    }
  }

  // Synthetic columns come first: unassigned, then manual work (positions
  // that never need a machine), then inspection (QA positions, machine-less
  // too but kept apart from generic manual labour). Pools follow ahead of
  // the machines they group, so the board reads from general to specific.
  const boardColumns = computed<BoardColumn[]>(() => {
    const columns: BoardColumn[] = []
    if (hasUnassignedOrders.value) {
      columns.push(syntheticColumn('unassigned', t('productionQueue.board.noMachine')))
    }
    columns.push(
      syntheticColumn('manual', t('productionQueue.board.manualWork')),
      syntheticColumn('inspection', t('productionQueue.board.inspection')),
      ...[...store.machinePools]
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((p) => ({
          key: poolColumnKey(p.id),
          kind: 'pool' as const,
          id: p.id,
          internal_name: p.name,
          vendor: '',
          model: '',
          poolMachineCount: p.machines.length,
          capabilities: poolCapabilityMethods(p),
        })),
      ...[...store.machines]
        .sort((a, b) => a.internal_name.localeCompare(b.internal_name))
        .map((m) => ({
          key: String(m.id),
          kind: 'machine' as const,
          id: m.id,
          internal_name: m.internal_name,
          vendor: m.vendor,
          model: m.model,
          poolMachineCount: null,
          capabilities: m.fabrication_methods,
        })),
    )
    return columns
  })

  return { boardColumns, positionFor, processMethodLabel, orderColumnKeyFor }
}
