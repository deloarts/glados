import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import type { InspectionMethodResponse } from '@/features/inspection-methods'
import { getMadeItems, useMadeItemFilesStore, useMadeItemPicturesStore } from '@/features/made-items'
import type { MadeItemFile, MadeItemResponse } from '@/features/made-items'
import { getOrder } from '@/features/orders'
import type { OrderResponse } from '@/features/orders'
import { reportImageFromBlob } from '@/shared/reports'
import { getLot } from '../../api/getLot'
import { getProductionOrderFiles } from '../../api/getProductionOrderFiles'
import { getProductionOrders } from '../../api/getProductionOrders'
import type { LotEventResponse, LotPositionProvisionResponse, LotResponse } from '../../types/productionLotsResponse'
import type { ProductionOrderFile, ProductionOrderResponse } from '../../types/productionOrdersResponse'
import { getLotEvents } from '../api/getLotEvents'
import { getLotPositionProvisions } from '../api/getLotPositionProvisions'

/**
 * Everything the inspection report of a lot shows, loaded when the report
 * is built so it reflects the lot at the time of export: the lot with its
 * route, every production order with its completions, the evidence files of
 * the inspection orders, the supplier orders and provisions of external
 * positions, the inspection methods, the made item with its picture and the
 * lot's history.
 */
export interface InspectionReportData {
  lot: LotResponse
  madeItem: MadeItemResponse | null
  madeItemFiles: MadeItemFile[]
  /** The part picture as a data URL, or null without one. */
  partImage: string | null
  productionOrders: ProductionOrderResponse[]
  filesByOrder: ReadonlyMap<number, ProductionOrderFile[]>
  ordersById: ReadonlyMap<number, OrderResponse>
  provisionsByPosition: ReadonlyMap<number, LotPositionProvisionResponse[]>
  methods: ReadonlyMap<number, InspectionMethodResponse>
  events: LotEventResponse[]
}

// The picture is printed about 5 cm tall.
const PART_IMAGE_HEIGHT = 600

function isInspectionPosition(lot: LotResponse, positionId: number): boolean {
  return (lot.positions ?? []).some((p) => p.id === positionId && (p.steps ?? []).some((s) => s.role === 'inspection'))
}

// The picture shown for the item everywhere else, at full size.
async function partPicture(madeItemId: number): Promise<string | null> {
  const pictures = useMadeItemPicturesStore()
  try {
    await pictures.fetchShown(madeItemId)
    const shown = pictures.getShown(madeItemId)
    if (!shown) return null
    return await reportImageFromBlob(
      await pictures.getBlob(madeItemId, shown.source, 'image'),
      PART_IMAGE_HEIGHT,
    )
  } catch {
    return null
  }
}

async function madeItemOf(lot: LotResponse): Promise<{ item: MadeItemResponse | null; files: MadeItemFile[] }> {
  if (lot.made_item_id === null) return { item: null, files: [] }
  const filesStore = useMadeItemFilesStore()
  const [page] = await Promise.all([getMadeItems({ id: lot.made_item_id, limit: 1 }), filesStore.fetchFiles(lot.made_item_id)])
  return { item: page.items[0] ?? null, files: filesStore.getFiles(lot.made_item_id) }
}

async function methodsById(): Promise<Map<number, InspectionMethodResponse>> {
  const store = useInspectionMethodsStore()
  if (store.items.length === 0) await store.refresh()
  return new Map(store.items.map((method) => [method.id, method]))
}

export async function loadInspectionReportData(lotId: number): Promise<InspectionReportData> {
  const lot = await getLot(lotId)
  const positions = lot.positions ?? []
  const externalPositions = positions.filter((p) => p.kind === 'external' || p.kind === 'mixed')
  const orderIds = [...new Set(positions.flatMap((p) => (p.order_id == null ? [] : [p.order_id])))]

  const [made, ordersPage, orders, provisions, methods, events] = await Promise.all([
    madeItemOf(lot),
    getProductionOrders({ lot_id: lot.id, limit: API_MAX_PAGE_SIZE }),
    Promise.all(orderIds.map((id) => getOrder(id))),
    Promise.all(externalPositions.map(async (p) => [p.id, await getLotPositionProvisions(lot.id, p.id)] as const)),
    methodsById(),
    getLotEvents(lot.id),
  ])
  const productionOrders = ordersPage.items
  const [files, partImage] = await Promise.all([
    Promise.all(
      productionOrders
        .filter((order) => order.lot_position_id != null && isInspectionPosition(lot, order.lot_position_id))
        .map(async (order) => [order.id, await getProductionOrderFiles(order.id)] as const),
    ),
    lot.made_item_id === null ? Promise.resolve(null) : partPicture(lot.made_item_id),
  ])

  return {
    lot,
    madeItem: made.item,
    madeItemFiles: made.files,
    partImage,
    productionOrders,
    filesByOrder: new Map(files),
    ordersById: new Map(orders.map((order) => [order.id, order])),
    provisionsByPosition: new Map(provisions),
    methods,
    events,
  }
}
