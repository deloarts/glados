import { describe, it, expect } from 'vitest'

import { aggregateItemUsage } from '../itemUsage'

import type { ItemOrderRow, ItemUsageDemand } from '../../types/itemDetail'
import type { OrderItemResponse, OrderResponse } from '@/features/orders'
import type { ProjectResponse } from '@/features/projects'

function demand(overrides: Partial<ItemUsageDemand> = {}): ItemUsageDemand {
  return {
    projectId: 1,
    projectNumber: 'P-100',
    projectCustomer: 'ACME',
    projectDescription: 'Widget line',
    projectStatus: 'active',
    quantity: 5,
    status: 'open',
    ...overrides,
  }
}

function orderRow(overrides: {
  order?: Partial<OrderResponse>
  orderItem?: Partial<OrderItemResponse>
}): ItemOrderRow {
  return {
    order: { id: 10, order_number: 'ORD-10', ...overrides.order } as OrderResponse,
    orderItem: {
      id: 1,
      status: 'delivered',
      project_id: 1,
      project_number: 'P-100',
      project_customer: 'ACME',
      project_description: 'Widget line',
      project_status: 'active',
      ...overrides.orderItem,
    } as OrderItemResponse,
  }
}

function project(id: number, overrides: Partial<ProjectResponse> = {}): ProjectResponse {
  return {
    id,
    project_number: `P-${id}`,
    product: null,
    ...overrides,
  } as ProjectResponse
}

describe('aggregateItemUsage', () => {
  it('returns nothing when there are no demands or order rows', () => {
    expect(aggregateItemUsage([], [], new Map())).toEqual([])
  })

  it('unions projects that appear only in demands and only in orders', () => {
    const rows = aggregateItemUsage(
      [demand({ projectId: 1, projectNumber: 'P-1' })],
      [orderRow({ order: { order_number: 'ORD-2' }, orderItem: { project_id: 2, project_number: 'P-2' } })],
      new Map(),
    )

    expect(rows.map((r) => r.projectId).sort()).toEqual([1, 2])
  })

  it('merges a project appearing in both inputs into a single row', () => {
    const rows = aggregateItemUsage(
      [demand({ projectId: 1, projectNumber: 'P-1' })],
      [orderRow({ orderItem: { project_id: 1, project_number: 'P-1' } })],
      new Map(),
    )

    expect(rows).toHaveLength(1)
  })

  it('sums quantity across demands for demanded, and only fulfilled ones for fulfilled', () => {
    const rows = aggregateItemUsage(
      [
        demand({ projectId: 1, quantity: 5, status: 'open' }),
        demand({ projectId: 1, quantity: 3, status: 'fulfilled' }),
        demand({ projectId: 1, quantity: 2, status: 'fulfilled' }),
      ],
      [],
      new Map(),
    )

    expect(rows[0]?.qtyDemanded).toBe(10)
    expect(rows[0]?.qtyFulfilled).toBe(5)
    expect(rows[0]?.demandCount).toBe(3)
  })

  it('only links orders whose order item is delivered', () => {
    const rows = aggregateItemUsage(
      [],
      [
        orderRow({ order: { id: 10, order_number: 'ORD-10' }, orderItem: { status: 'delivered' } }),
        orderRow({ order: { id: 11, order_number: 'ORD-11' }, orderItem: { status: 'ordered' } }),
      ],
      new Map(),
    )

    expect(rows[0]?.fulfilledOrders).toEqual([{ orderId: 10, orderNumber: 'ORD-10' }])
  })

  it('deduplicates the same order across multiple delivered order items', () => {
    const rows = aggregateItemUsage(
      [],
      [
        orderRow({ order: { id: 10, order_number: 'ORD-10' }, orderItem: { id: 1, status: 'delivered' } }),
        orderRow({ order: { id: 10, order_number: 'ORD-10' }, orderItem: { id: 2, status: 'delivered' } }),
      ],
      new Map(),
    )

    expect(rows[0]?.fulfilledOrders).toEqual([{ orderId: 10, orderNumber: 'ORD-10' }])
  })


  it('resolves product fields from the project lookup, falling back to null', () => {
    const withProduct = project(1, {
      product: { product_number: 'PR-1', description: 'A product' } as ProjectResponse['product'],
    })
    const rows = aggregateItemUsage(
      [demand({ projectId: 1 }), demand({ projectId: 2, projectNumber: 'P-2' })],
      [],
      new Map([[1, withProduct]]),
    )

    const row1 = rows.find((r) => r.projectId === 1)
    const row2 = rows.find((r) => r.projectId === 2)
    expect(row1?.productNumber).toBe('PR-1')
    expect(row1?.productDescription).toBe('A product')
    // Project 2 was never in the lookup map at all.
    expect(row2?.productNumber).toBeNull()
    expect(row2?.productDescription).toBeNull()
  })

  it('falls back to null product fields when the looked-up project has none', () => {
    const rows = aggregateItemUsage([demand({ projectId: 1 })], [], new Map([[1, project(1)]]))

    expect(rows[0]?.productNumber).toBeNull()
    expect(rows[0]?.productDescription).toBeNull()
  })

  it('sorts rows by project number descending', () => {
    const rows = aggregateItemUsage(
      [
        demand({ projectId: 1, projectNumber: 'P-1' }),
        demand({ projectId: 20, projectNumber: 'P-20' }),
        demand({ projectId: 3, projectNumber: 'P-3' }),
      ],
      [],
      new Map(),
    )

    expect(rows.map((r) => r.projectNumber)).toEqual(['P-20', 'P-3', 'P-1'])
  })
})
