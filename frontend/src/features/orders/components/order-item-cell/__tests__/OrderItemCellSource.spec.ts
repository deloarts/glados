import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import { i18n } from '@/core/i18n'
import { makeOrderItemResponse } from '@/test-utils/factories'

import OrderItemCellSource from '../OrderItemCellSource.vue'
import type { OrderItemResponse } from '../../../types/ordersResponse'

function makeItem(overrides: Partial<OrderItemResponse> = {}): OrderItemResponse {
  return makeOrderItemResponse({
    line_type: 'SOURCE',
    bought_item_id: null,
    source_item_id: 5,
    item_article_name: 'D20',
    item_specification: '1.0037 | Round bar',
    item_order_code_1: '',
    ...overrides,
  })
}

function mountCell(item: OrderItemResponse) {
  return mount(OrderItemCellSource, {
    props: { item },
    global: { plugins: [i18n] },
  })
}

describe('OrderItemCellSource', () => {
  it('renders name, specification, and both order codes when all are set', () => {
    const wrapper = mountCell(makeItem({ item_order_code_1: 'SC-1', item_order_code_2: 'SC-2' }))
    const rows = wrapper.findAll('.item-name, .item-code')
    expect(rows).toHaveLength(4)
    expect(rows[0]!.text()).toBe('D20')
    expect(rows[1]!.text()).toBe('1.0037 | Round bar')
    expect(rows[2]!.text()).toBe('SC-1')
    expect(rows[3]!.text()).toBe('SC-2')
  })

  it('renders only the name when no specification or codes are set', () => {
    const wrapper = mountCell(
      makeItem({ item_specification: '', item_order_code_1: '', item_order_code_2: null }),
    )
    const rows = wrapper.findAll('.item-name, .item-code')
    expect(rows).toHaveLength(1)
    expect(rows[0]!.text()).toBe('D20')
  })

  it('renders name plus specification when only the specification is set', () => {
    const wrapper = mountCell(makeItem({ item_order_code_1: '', item_order_code_2: null }))
    const rows = wrapper.findAll('.item-name, .item-code')
    expect(rows).toHaveLength(2)
    expect(rows[1]!.text()).toBe('1.0037 | Round bar')
  })

  it('renders "Substitute for" when the line carries demand substitutions', () => {
    const wrapper = mountCell(
      makeItem({
        demand_substitutions: [
          {
            demand_item_id: 9,
            original_item_id: 3,
            original_item_order_code_1: 'RB-3',
            original_item_article_name: 'D16',
            substitute_reason: 'Out of stock',
            quantity: 2,
          },
        ],
      }),
    )
    const subst = wrapper.find('.subst-for')
    expect(subst.exists()).toBe(true)
    expect(subst.find('.subst-for-label').text()).toBe('D16 - RB-3')
  })
})
