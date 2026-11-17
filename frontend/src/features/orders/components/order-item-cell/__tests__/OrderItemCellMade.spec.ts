import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { makeOrderItemResponse } from '@/test-utils/factories'

import OrderItemCellMade from '../OrderItemCellMade.vue'
import type { OrderItemResponse } from '../../../types/ordersResponse'

function makeItem(overrides: Partial<OrderItemResponse> = {}): OrderItemResponse {
  return makeOrderItemResponse({
    line_type: 'MADE',
    bought_item_id: null,
    made_item_id: 9,
    item_article_name: 'Bracket',
    item_part_number: 'PN-1',
    item_order_code_1: '',
    lot_id: 3,
    lot_number: 'LOT-0003',
    fabrication_method: 'Milling',
    ...overrides,
  })
}

function mountCell(item: OrderItemResponse) {
  return mount(OrderItemCellMade, {
    props: { item },
    global: { plugins: [createPinia(), i18n] },
  })
}

describe('OrderItemCellMade', () => {
  it('renders the part number as a clickable link when it is set', () => {
    const wrapper = mountCell(makeItem())
    const link = wrapper.get('.item-link')
    expect(link.text()).toBe('PN-1')
  })

  it('appends the revision to the part number label when present', () => {
    const wrapper = mountCell(makeItem({ item_revision: 'A' }))
    const link = wrapper.get('.item-link')
    expect(link.text()).toBe('PN-1:A')
  })

  it('shows a warning instead of the part number when it is missing', () => {
    const wrapper = mountCell(makeItem({ item_part_number: null }))
    expect(wrapper.find('.item-link').exists()).toBe(false)
    const warning = wrapper.get('.item-name-warning')
    expect(warning.find('i').exists()).toBe(true)
    expect(warning.text()).toBe(i18n.global.t('orders.items.noPartNumber'))
  })

  it('emits openItem with the made item id when the part number link is clicked', async () => {
    const wrapper = mountCell(makeItem())
    await wrapper.get('.item-link').trigger('click')
    expect(wrapper.emitted('openItem')).toEqual([[9]])
  })
})
