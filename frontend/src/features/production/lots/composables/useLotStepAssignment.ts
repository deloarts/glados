import { computed, ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { getMachinePools, getProductionMachines } from '@/features/production-machines'
import { getOrders, OPEN_ORDER_STATUSES } from '@/features/orders'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { useMachineCapability } from '../../composables/useMachineCapability'
import { parseAssignTargetKey } from '../utils/lotStepAssignOptions'
import { targetKeyFor } from '../utils/lotStepPositionOrders'
import { MADE_ITEM_ORDER_UNIT } from '../../utils/madeItemOrderUnit'

import type { MachinePoolResponse, ProductionMachineResponse } from '@/features/production-machines'
import type { OrderResponse } from '@/features/orders'
import type {
  LotPositionProductionOrderSummary,
  LotPositionResponse,
} from '../../types/productionLotsResponse'

export interface LotStepAssignmentProps {
  lotId: number
  staged?: boolean
}

// Staged mode emits these instead of writing; the host's draft holds them
// until its Save resolves them for real.
export interface LotStepAssignmentIntents {
  assignPosition: (positionId: number, key: string) => void
  clearAssignment: (positionId: number) => void
  reassignOrder: (orderId: number, key: string | null) => void
  clearReassignment: (orderId: number) => void
}

/**
 * Assignment state of the lot step list's Machine / Order column: the
 * machines, pools and open purchase orders offered as targets, reassigning a
 * queued order's machine or pool, assigning an unassigned position, and the
 * create-order and order-detail dialogs reached from that column.
 */
export function useLotStepAssignment(
  props: LotStepAssignmentProps,
  positionsById: Ref<Map<number, LotPositionResponse>>,
  intents: LotStepAssignmentIntents,
) {
  const { t } = useI18n()
  const { withErrorToast } = useErrorToast()
  const detailStore = useProductionLotDetailStore()
  const queueStore = useProductionQueueStore()
  const { getPreferredSupplierId } = useMachineCapability()

  const machines = ref<ProductionMachineResponse[]>([])
  const loadingMachines = ref(false)

  async function loadMachines(): Promise<void> {
    loadingMachines.value = true
    try {
      const result = await getProductionMachines({ limit: API_MAX_PAGE_SIZE })
      machines.value = result.items
    } finally {
      loadingMachines.value = false
    }
  }

  const pools = ref<MachinePoolResponse[]>([])
  const loadingPools = ref(false)

  async function loadPools(): Promise<void> {
    loadingPools.value = true
    try {
      const result = await getMachinePools({ limit: API_MAX_PAGE_SIZE })
      pools.value = result.items
    } finally {
      loadingPools.value = false
    }
  }

  const orders = ref<OrderResponse[]>([])
  const loadingOrders = ref(false)

  async function loadOrders(): Promise<void> {
    loadingOrders.value = true
    try {
      const result = await getOrders({ status: [...OPEN_ORDER_STATUSES], limit: API_MAX_PAGE_SIZE })
      orders.value = result.items
    } finally {
      loadingOrders.value = false
    }
  }

  const assigningOrderId = ref<number | null>(null)

  // A pool key reassigns with { machinePoolId } and the server clears
  // machine_id; a machine key sends the plain id.
  async function onTargetChange(orderId: number, key: string | null): Promise<void> {
    assigningOrderId.value = orderId
    await withErrorToast(
      async () => {
        const target = !key
          ? null
          : key.startsWith('pool:')
            ? { machinePoolId: Number(key.slice('pool:'.length)) }
            : Number(key.slice('machine:'.length))
        await queueStore.reassignMachine(orderId, target)
        await detailStore.refetch()
      },
      { summary: t('production.lots.detail.manageProduction.errors.unknown') },
    )
    assigningOrderId.value = null
  }

  // In staged mode, picking the order's own current target again drops the
  // pending entry instead of keeping a no-op override.
  async function onReassignChange(
    order: LotPositionProductionOrderSummary,
    key: string | null,
  ): Promise<void> {
    if (!props.staged) {
      await onTargetChange(order.id, key)
      return
    }
    if (key === targetKeyFor(order)) {
      intents.clearReassignment(order.id)
    } else {
      intents.reassignOrder(order.id, key)
    }
  }

  const assigningPositionId = ref<number | null>(null)
  const showCreateOrder = ref(false)
  const createOrderPositionId = ref<number | null>(null)
  const showOrderDetail = ref(false)
  const orderDetailOrderId = ref<number | null>(null)

  // Pre-fills the new order's supplier with the position's preferred one;
  // the form's own supplier field always wins.
  const createOrderPresetSupplierId = computed<number | null>(() => {
    if (createOrderPositionId.value === null) return null
    const position = positionsById.value.get(createOrderPositionId.value)
    return position ? getPreferredSupplierId(position) : null
  })

  function openOrderDetail(orderId: number | null): void {
    if (orderId === null) return
    orderDetailOrderId.value = orderId
    showOrderDetail.value = true
  }

  async function onAssignTargetChange(
    position: LotPositionResponse,
    key: string | null,
  ): Promise<void> {
    if (key === null) {
      // Only the staged Select has a clear button.
      if (props.staged) intents.clearAssignment(position.id)
      return
    }

    const parsed = parseAssignTargetKey(key)
    if (!parsed) return

    // Opening the create-order dialog is not a write in either mode;
    // onOrderCreated assigns (or stages) the order once it exists.
    if (parsed.kind === 'create') {
      createOrderPositionId.value = position.id
      showCreateOrder.value = true
      return
    }

    if (props.staged) {
      intents.assignPosition(position.id, key)
      return
    }

    assigningPositionId.value = position.id
    await withErrorToast(
      async () => {
        if (parsed.kind === 'order') {
          await detailStore.assignPosition(props.lotId, position.id, {
            order_id: parsed.id,
            unit: MADE_ITEM_ORDER_UNIT,
            items_per_unit: 1,
            price: null,
            expected_delivery_date: null,
            expected_pickup_date: null,
            quantity: position.quantity_remaining,
          })
          return
        }
        const orderInput =
          parsed.kind === 'pool'
            ? { machine_pool_id: parsed.id, quantity: position.quantity_remaining }
            : parsed.kind === 'machine'
              ? { machine_id: parsed.id, quantity: position.quantity_remaining }
              : { machine_id: null, quantity: position.quantity_remaining }
        await detailStore.assignInternal(props.lotId, position.id, { orders: [orderInput] })
        await queueStore.fetchOrders()
      },
      { summary: t('production.lots.detail.steps.assignError') },
    )
    assigningPositionId.value = null
  }

  // The dialog only knows the order it created, so the requesting position
  // is remembered when 'order:new' is picked and consumed here.
  async function onOrderCreated(order: OrderResponse): Promise<void> {
    const positionId = createOrderPositionId.value
    createOrderPositionId.value = null
    if (positionId === null) return
    const position = positionsById.value.get(positionId)
    if (!position) return
    await onAssignTargetChange(position, `order:${order.id}`)
  }

  return {
    machines,
    loadingMachines,
    loadMachines,
    pools,
    loadingPools,
    loadPools,
    orders,
    loadingOrders,
    loadOrders,
    assigningOrderId,
    onReassignChange,
    assigningPositionId,
    showCreateOrder,
    showOrderDetail,
    orderDetailOrderId,
    createOrderPresetSupplierId,
    openOrderDetail,
    onAssignTargetChange,
    onOrderCreated,
  }
}
