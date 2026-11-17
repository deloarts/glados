import { ref, watch } from 'vue'
import type { Ref } from 'vue'

import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { getDemands } from '@/features/bought-items'
import type { BoughtItemDemandResponse } from '@/features/bought-items'
import { getMadeItemDemands } from '@/features/made-items'
import type { MadeItemDemandResponse } from '@/features/made-items'
import { getOrders } from '@/features/orders'
import type { OrderResponse } from '@/features/orders'
import type { ProjectSummaryResponse } from '@/features/projects'
import { getSourceItemDemands } from '@/features/source-items'
import type { SourceItemDemandResponse } from '@/features/source-items'
import { getProductSummary } from '@/features/products'

/**
 * The bill of material, orders and costs of all projects built on a
 * product, for its Bill of Material, Orders and Costs tabs. They load
 * together the first time one of those tabs opens, not with the page,
 * and again for another product. The lists render without a paginator, so
 * they request the API maximum.
 */
export function useProductProcurement(productId: Ref<number>) {
  const summary = ref<ProjectSummaryResponse | null>(null)
  const boughtDemands = ref<BoughtItemDemandResponse[]>([])
  const madeDemands = ref<MadeItemDemandResponse[]>([])
  const sourceDemands = ref<SourceItemDemandResponse[]>([])
  const orders = ref<OrderResponse[]>([])
  const loading = ref(false)
  const failed = ref(false)

  // The product the lists were last requested for; null until then.
  let requestedFor: number | null = null

  async function ensureLoaded(): Promise<void> {
    const id = productId.value
    if (requestedFor === id) return
    requestedFor = id
    loading.value = true
    failed.value = false
    try {
      const [summaryData, boughtPage, madePage, sourcePage, ordersPage] = await Promise.all([
        getProductSummary(id),
        // Ordered by manufacturer, so a list cut at the ceiling is still a
        // meaningful head. Made and source demands lack this sort key.
        getDemands({ product_id: id, limit: API_MAX_PAGE_SIZE, order_by: 'manufacturer_name', order_dir: 'asc' }),
        getMadeItemDemands({ product_id: id, limit: API_MAX_PAGE_SIZE }),
        getSourceItemDemands({ product_id: id, limit: API_MAX_PAGE_SIZE }),
        getOrders({ product_id: id, limit: API_MAX_PAGE_SIZE }),
      ])
      if (productId.value !== id) return
      summary.value = summaryData
      boughtDemands.value = boughtPage.items
      madeDemands.value = madePage.items
      sourceDemands.value = sourcePage.items
      orders.value = ordersPage.items
    } catch {
      if (productId.value !== id) return
      failed.value = true
      // A later visit to the tab tries again.
      requestedFor = null
    } finally {
      if (productId.value === id) loading.value = false
    }
  }

  watch(productId, () => {
    requestedFor = null
    summary.value = null
    boughtDemands.value = []
    madeDemands.value = []
    sourceDemands.value = []
    orders.value = []
    failed.value = false
  })

  return { summary, boughtDemands, madeDemands, sourceDemands, orders, loading, failed, ensureLoaded }
}
