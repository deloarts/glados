import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import CatalogueItemOrdersCard from '../CatalogueItemOrdersCard.vue'

import type { ItemOrderRow } from '../../types/itemDetail'
import type { OrderItemResponse, OrderResponse } from '@/features/orders'

function orderRow(overrides: {
  order?: Partial<OrderResponse>
  orderItem?: Partial<OrderItemResponse>
} = {}): ItemOrderRow {
  return {
    order: {
      id: 10,
      order_number: 'ORD-10',
      status: 'delivered',
      supplier_name: 'ACME Supply',
      ordered_date: '2026-03-01T00:00:00Z',
      ...overrides.order,
    } as OrderResponse,
    orderItem: {
      id: 1,
      status: 'delivered',
      quantity: 5,
      unit: 'PCS',
      project_number: 'P-100',
      delivery_date: '2026-03-10T00:00:00Z',
      price: 12,
      ...overrides.orderItem,
    } as OrderItemResponse,
  }
}

interface Props {
  rows: ItemOrderRow[]
  loading: boolean
  error: boolean
  truncated: boolean
  limit: number
}

function mountCard(props: Partial<Props> = {}) {
  return mountWithApp(CatalogueItemOrdersCard, {
    props: { rows: [], loading: false, error: false, truncated: false, limit: 200, ...props },
  })
}

describe('CatalogueItemOrdersCard', () => {
  it('shows the empty state when there are no rows', () => {
    const wrapper = mountCard()
    expect(wrapper.text()).toContain('This item has not been ordered yet.')
  })

  it('shows a loading spinner only while there are no rows yet', () => {
    expect(mountCard({ loading: true }).find('.loading-state').exists()).toBe(true)
    expect(mountCard({ loading: true, rows: [orderRow()] }).find('.loading-state').exists()).toBe(false)
  })

  it('shows the section error state', () => {
    expect(mountCard({ error: true }).text()).toContain('Could not load this section.')
  })

  it('shows the truncation notice with the limit', () => {
    expect(mountCard({ rows: [orderRow()], truncated: true, limit: 200 }).text()).toContain(
      'Showing the first 200 entries only.',
    )
  })

  it('renders a row per order item with order number, supplier and quantity', () => {
    const wrapper = mountCard({ rows: [orderRow()] })
    expect(wrapper.text()).toContain('ORD-10')
    expect(wrapper.text()).toContain('ACME Supply')
    expect(wrapper.text()).toContain('5 pcs')
    expect(wrapper.text()).toContain('P-100')
  })

  it('emits open-order with the order id when the order number is clicked', async () => {
    const wrapper = mountCard({ rows: [orderRow({ order: { id: 42, order_number: 'ORD-42' } })] })
    await wrapper.find('.order-link').trigger('click')
    expect(wrapper.emitted('open-order')).toEqual([[42]])
  })

  it('formats the unit code through formatUnit rather than showing the raw stored code', () => {
    const wrapper = mountCard({ rows: [orderRow({ orderItem: { unit: 'M2' } })] })
    expect(wrapper.text()).not.toContain('M2')
    expect(wrapper.text()).toContain('m²')
  })
})
