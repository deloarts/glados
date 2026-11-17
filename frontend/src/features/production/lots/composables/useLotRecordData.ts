import { ref } from 'vue'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'

import { getProjects } from '@/features/projects'
import { getMadeItems } from '@/features/made-items'
import { getBoughtItems } from '@/features/bought-items'
import { sourceItemsApi } from '@/features/source-items'
import { getOrder } from '@/features/orders'
import { getLotDemands } from '../api/getLotDemands'
import { getProductionOrders } from '../../api/getProductionOrders'
import { getProductionOrderFiles } from '../../api/getProductionOrderFiles'
import { getLotPositionProvisions } from '../api/getLotPositionProvisions'

import type { ProjectResponse } from '@/features/projects'
import type { MadeItemResponse } from '@/features/made-items'
import type { BoughtItemResponse } from '@/features/bought-items'
import type { SourceItemResponse } from '@/features/source-items'
import type {
  LotDemandResponse,
  LotPositionProvisionResponse,
  LotPositionResponse,
  LotResponse,
} from '../../types/productionLotsResponse'
import type {
  ManufacturingAssessmentResponse,
  ProductionOrderFile,
  ProductionOrderResponse,
} from '../../types/productionOrdersResponse'
import type { OrderItemResponse, OrderResponse } from '@/features/orders'

export type LotSourceItem =
  | { kind: 'bought'; item: BoughtItemResponse }
  | { kind: 'source'; item: SourceItemResponse }
  | { kind: 'made'; item: MadeItemResponse }

/**
 * Data the read-only lot record needs beyond LotResponse: project, made
 * item, source item, covered demands, the lot's full order history
 * including finished orders, and the evidence files of its inspection orders.
 */
export function useLotRecordData() {
  const project = ref<ProjectResponse | null>(null)
  const madeItem = ref<MadeItemResponse | null>(null)
  const sourceItem = ref<LotSourceItem | null>(null)
  const demands = ref<LotDemandResponse[]>([])
  const productionOrders = ref<ProductionOrderResponse[]>([])
  const provisionsByPosition = ref<Record<number, LotPositionProvisionResponse[]>>({})
  // QA evidence lives on the orders of inspection positions.
  const filesByOrder = ref<Record<number, ProductionOrderFile[]>>({})
  // Orders behind external fulfillment, keyed by id so shared orders are
  // fetched once.
  const ordersById = ref<Map<number, OrderResponse>>(new Map())
  const loading = ref(false)
  const { hasPermission } = usePermissions()

  async function loadProject(projectId: number): Promise<void> {
    const page = await getProjects({ id: projectId, limit: 1 })
    project.value = page.items[0] ?? null
  }

  async function loadMadeItem(madeItemId: number): Promise<void> {
    const page = await getMadeItems({ id: madeItemId, limit: 1 })
    madeItem.value = page.items[0] ?? null
  }

  async function loadSourceItem(lot: LotResponse): Promise<void> {
    if (lot.source_bought_item_id !== null) {
      const page = await getBoughtItems({ id: lot.source_bought_item_id, limit: 1 })
      sourceItem.value = page.items[0] ? { kind: 'bought', item: page.items[0] } : null
    } else if (lot.source_made_item_id !== null) {
      const page = await getMadeItems({ id: lot.source_made_item_id, limit: 1 })
      sourceItem.value = page.items[0] ? { kind: 'made', item: page.items[0] } : null
    } else if (lot.source_item_id !== null) {
      const page = await sourceItemsApi.list({ id: lot.source_item_id, limit: 1 })
      sourceItem.value = page.items[0] ? { kind: 'source', item: page.items[0] } : null
    } else {
      sourceItem.value = null
    }
  }

  async function loadDemands(lotId: number): Promise<void> {
    demands.value = await getLotDemands(lotId)
  }

  async function loadProductionOrders(lot: LotResponse): Promise<void> {
    const page = await getProductionOrders({ lot_id: lot.id, limit: API_MAX_PAGE_SIZE })
    productionOrders.value = page.items
    await loadEvidenceFiles(lot, page.items)
  }

  async function loadEvidenceFiles(
    lot: LotResponse,
    orders: ProductionOrderResponse[],
  ): Promise<void> {
    // Reading evidence needs write:inspections, the right of whoever records
    // it, so a user without it would only collect a 403 per order.
    if (!hasPermission(Permission.WRITE_INSPECTIONS)) {
      filesByOrder.value = {}
      return
    }
    const inspectionPositionIds = new Set(
      (lot.positions ?? [])
        .filter((p) => (p.steps ?? []).some((s) => s.role === 'inspection'))
        .map((p) => p.id),
    )
    const entries = await Promise.all(
      orders
        .filter((o) => inspectionPositionIds.has(o.lot_position_id))
        .map(async (o) => [o.id, await getProductionOrderFiles(o.id)] as const),
    )
    filesByOrder.value = Object.fromEntries(entries)
  }

  // Only positions with an external leg have provisions.
  async function loadProvisions(lot: LotResponse): Promise<void> {
    const externalPositions = (lot.positions ?? []).filter(
      (p) => p.kind === 'external' || p.kind === 'mixed',
    )
    const entries = await Promise.all(
      externalPositions.map(
        async (p) => [p.id, await getLotPositionProvisions(lot.id, p.id)] as const,
      ),
    )
    provisionsByPosition.value = Object.fromEntries(entries)
  }

  async function loadOrders(lot: LotResponse): Promise<void> {
    const orderIds = new Set<number>()
    if (lot.source_order_id) orderIds.add(lot.source_order_id)
    for (const position of lot.positions ?? []) {
      if (
        (position.kind === 'external' || position.kind === 'mixed') &&
        position.order_id != null
      ) {
        orderIds.add(position.order_id)
      }
    }
    const orders = await Promise.all([...orderIds].map((id) => getOrder(id)))
    ordersById.value = new Map(orders.map((o) => [o.id, o]))
  }

  async function load(lot: LotResponse): Promise<void> {
    loading.value = true
    try {
      await Promise.all([
        loadProject(lot.project_id),
        loadMadeItem(lot.made_item_id),
        loadSourceItem(lot),
        loadDemands(lot.id),
        loadProductionOrders(lot),
        loadProvisions(lot),
        loadOrders(lot),
      ])
    } finally {
      loading.value = false
    }
  }

  function ordersForPosition(positionId: number): ProductionOrderResponse[] {
    return productionOrders.value.filter((o) => o.lot_position_id === positionId)
  }

  function provisionsForPosition(positionId: number): LotPositionProvisionResponse[] {
    return provisionsByPosition.value[positionId] ?? []
  }

  function filesForOrder(orderId: number): ProductionOrderFile[] {
    return filesByOrder.value[orderId] ?? []
  }

  // Embedded on the order by the backend.
  function assessmentForOrder(orderId: number): ManufacturingAssessmentResponse | null {
    return productionOrders.value.find((o) => o.id === orderId)?.assessment ?? null
  }

  // The order line item fulfilling an external or mixed position, with more
  // detail than the position's denormalized fields.
  function orderItemForPosition(position: LotPositionResponse): OrderItemResponse | null {
    if (position.order_id == null) return null
    const order = ordersById.value.get(position.order_id)
    return order?.items?.find((i) => i.lot_position_id === position.id) ?? null
  }

  function orderById(orderId: number | null): OrderResponse | null {
    return orderId === null ? null : (ordersById.value.get(orderId) ?? null)
  }

  return {
    project,
    madeItem,
    sourceItem,
    demands,
    productionOrders,
    loading,
    load,
    ordersForPosition,
    provisionsForPosition,
    filesForOrder,
    assessmentForOrder,
    orderItemForPosition,
    orderById,
  }
}
