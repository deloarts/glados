import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import CatalogueItemUsageCard from '../CatalogueItemUsageCard.vue'

import type { ItemUsageRow } from '../../types/itemDetail'

function row(overrides: Partial<ItemUsageRow> = {}): ItemUsageRow {
  return {
    projectId: 1,
    projectNumber: 'P-100',
    projectCustomer: 'ACME',
    projectDescription: 'Widget line',
    projectStatus: 'active',
    productNumber: 'PR-1',
    productDescription: 'A product',
    qtyDemanded: 10,
    qtyFulfilled: 4,
    demandCount: 2,
    fulfilledOrders: [],
    ...overrides,
  }
}

interface Props {
  rows: ItemUsageRow[]
  loading: boolean
  error: boolean
}

function mountCard(props: Partial<Props> = {}) {
  return mountWithApp(CatalogueItemUsageCard, {
    props: { rows: [], loading: false, error: false, ...props },
  })
}

describe('CatalogueItemUsageCard', () => {
  it('shows the empty state when there are no rows', () => {
    expect(mountCard().text()).toContain('This item is not used in any project yet.')
  })

  it('shows a loading spinner only while there are no rows yet', () => {
    expect(mountCard({ loading: true }).find('.loading-state').exists()).toBe(true)
    expect(mountCard({ loading: true, rows: [row()] }).find('.loading-state').exists()).toBe(false)
  })

  it('shows the section error state', () => {
    expect(mountCard({ error: true }).text()).toContain('Could not load this section.')
  })

  it('renders project, customer, product, quantities', () => {
    const wrapper = mountCard({ rows: [row()] })
    expect(wrapper.text()).toContain('P-100')
    expect(wrapper.text()).toContain('ACME')
    expect(wrapper.text()).toContain('PR-1')
    expect(wrapper.text()).toContain('10')
    expect(wrapper.text()).toContain('4')
  })

  it('shows the no-product placeholder when productNumber is null', () => {
    const wrapper = mountCard({ rows: [row({ productNumber: null })] })
    expect(wrapper.text()).toContain('No product')
  })

  it('translates a known project status', () => {
    const wrapper = mountCard({ rows: [row({ projectStatus: 'on_hold' })] })
    expect(wrapper.text()).toContain('On Hold')
  })

  it('shows the no-orders placeholder when there are no fulfilled orders', () => {
    const wrapper = mountCard({ rows: [row({ fulfilledOrders: [] })] })
    expect(wrapper.find('.orders-empty').exists()).toBe(true)
  })

  it('renders a link per fulfilled order and emits open-order on click', async () => {
    const wrapper = mountCard({
      rows: [row({ fulfilledOrders: [{ orderId: 5, orderNumber: 'ORD-5' }] })],
    })
    expect(wrapper.text()).toContain('ORD-5')
    await wrapper.find('.order-link').trigger('click')
    expect(wrapper.emitted('open-order')).toEqual([[5]])
  })
})
