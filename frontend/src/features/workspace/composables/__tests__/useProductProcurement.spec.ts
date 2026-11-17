import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'

import type { PageResponse } from '@/core/api/types'
import type { ProjectSummaryResponse } from '@/features/projects'

const page = <T>(items: T[]): PageResponse<T> => ({ items, total: items.length, limit: 500, skip: 0 })

const getProductSummary = vi.fn<(id: number) => Promise<ProjectSummaryResponse>>()
const getDemands = vi.fn<(params: unknown) => Promise<PageResponse<{ id: number }>>>()
const getMadeItemDemands = vi.fn<(params: unknown) => Promise<PageResponse<{ id: number }>>>()
const getSourceItemDemands = vi.fn<(params: unknown) => Promise<PageResponse<{ id: number }>>>()
const getOrders = vi.fn<(params: unknown) => Promise<PageResponse<{ id: number }>>>()

vi.mock('@/features/products/api/getProductSummary', () => ({ getProductSummary: (id: number) => getProductSummary(id) }))
vi.mock('@/features/bought-items', () => ({ getDemands: (p: unknown) => getDemands(p) }))
vi.mock('@/features/made-items', () => ({ getMadeItemDemands: (p: unknown) => getMadeItemDemands(p) }))
vi.mock('@/features/source-items', () => ({ getSourceItemDemands: (p: unknown) => getSourceItemDemands(p) }))
vi.mock('@/features/orders', () => ({ getOrders: (p: unknown) => getOrders(p) }))

import { useProductProcurement } from '../useProductProcurement'

function summary(order_count: number): ProjectSummaryResponse {
  return { cost_by_supplier: [], demand_counts: {}, order_count, total_delivered_cost: 0, total_ordered_cost: 0 }
}

describe('useProductProcurement', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getProductSummary.mockResolvedValue(summary(2))
    getDemands.mockResolvedValue(page([{ id: 1 }]))
    getMadeItemDemands.mockResolvedValue(page([{ id: 2 }]))
    getSourceItemDemands.mockResolvedValue(page([{ id: 3 }]))
    getOrders.mockResolvedValue(page([{ id: 4 }, { id: 5 }]))
  })

  it('loads everything of the product once, across all its projects', async () => {
    const procurement = useProductProcurement(ref(9))

    await procurement.ensureLoaded()
    await procurement.ensureLoaded()

    expect(getProductSummary).toHaveBeenCalledTimes(1)
    expect(getProductSummary).toHaveBeenCalledWith(9)
    expect(getDemands).toHaveBeenCalledWith(expect.objectContaining({ product_id: 9 }))
    expect(getMadeItemDemands).toHaveBeenCalledWith(expect.objectContaining({ product_id: 9 }))
    expect(getSourceItemDemands).toHaveBeenCalledWith(expect.objectContaining({ product_id: 9 }))
    expect(getOrders).toHaveBeenCalledWith(expect.objectContaining({ product_id: 9 }))
    expect(procurement.summary.value?.order_count).toBe(2)
    expect(procurement.orders.value).toHaveLength(2)
    expect(procurement.loading.value).toBe(false)
  })

  it('loads again for another product and drops the old lists', async () => {
    const productId = ref(9)
    const procurement = useProductProcurement(productId)
    await procurement.ensureLoaded()

    productId.value = 10
    await flushPromises()
    expect(procurement.orders.value).toEqual([])

    await procurement.ensureLoaded()
    expect(getProductSummary).toHaveBeenLastCalledWith(10)
  })

  it('reports a failure and tries again on the next call', async () => {
    getOrders.mockRejectedValueOnce(new Error('offline'))
    const procurement = useProductProcurement(ref(9))

    await procurement.ensureLoaded()
    expect(procurement.failed.value).toBe(true)

    await procurement.ensureLoaded()
    expect(procurement.failed.value).toBe(false)
    expect(getProductSummary).toHaveBeenCalledTimes(2)
  })
})
