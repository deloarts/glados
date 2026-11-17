import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeDemandItemResponse } from '@/test-utils/factories'
import { useBoughtItemsAllocationsStore } from '../../stores/boughtItemsAllocationsStore'
import BoughtItemDemandAllocationCell from '../BoughtItemDemandAllocationCell.vue'
import BoughtItemDemandItemCell from '../BoughtItemDemandItemCell.vue'
import BoughtItemDemandOrderCell from '../BoughtItemDemandOrderCell.vue'

import type { Component } from 'vue'
import type { DemandSummaryResponse } from '@/features/bought-items'

function makeSummary(overrides: Partial<DemandSummaryResponse> = {}): DemandSummaryResponse {
  return {
    allocated: 0,
    delivered: 0,
    demand_item_id: 1,
    fulfilled_from_stock: 0,
    in_transit: 0,
    is_fully_allocated: false,
    is_fully_delivered: false,
    order_ids: [],
    order_numbers: [],
    ordered: 0,
    pending: 0,
    remaining: 5,
    substitutions: [],
    total: 5,
    unallocated: 5,
    unit: 'PCS',
    unit_mismatch: false,
    ...overrides,
  }
}

function mountCell(
  component: Component,
  props: Record<string, unknown>,
  summary?: DemandSummaryResponse,
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  if (summary) useBoughtItemsAllocationsStore().summaries = { 1: summary }
  return mountWithApp(component, { pinia, props, global: { directives: { tooltip: Tooltip } } })
}

describe('BoughtItemDemandAllocationCell', () => {
  it('shows what is allocated of the total and the open rest', () => {
    const wrapper = mountCell(
      BoughtItemDemandAllocationCell,
      { demandId: 1, status: 'open' },
      makeSummary({ allocated: 2, fulfilled_from_stock: 1, unallocated: 2 }),
    )

    expect(wrapper.find('.alloc-numbers').text()).toMatch(/^3\s*\/\s*5/)
    expect(wrapper.find('.alloc-tag').text()).toBe('-2')
    expect(wrapper.find('[data-testid="alloc-from-stock"]').exists()).toBe(true)
  })

  it('shows a check once nothing is left to allocate', () => {
    const wrapper = mountCell(
      BoughtItemDemandAllocationCell,
      { demandId: 1, status: 'open' },
      makeSummary({ allocated: 5, unallocated: 0 }),
    )

    expect(wrapper.find('.alloc-tag').exists()).toBe(false)
    expect(wrapper.find('[data-testid="alloc-complete"]').exists()).toBe(true)
  })

  it.each(['fulfilled', 'canceled'])('shows no open rest on an ended demand (%s)', (status) => {
    const wrapper = mountCell(
      BoughtItemDemandAllocationCell,
      { demandId: 1, status },
      makeSummary({ allocated: 2, unallocated: 3 }),
    )

    expect(wrapper.find('.alloc-numbers').text()).toMatch(/^2\s*\/\s*5/)
    expect(wrapper.find('.alloc-tag').exists()).toBe(false)
    expect(wrapper.find('[data-testid="alloc-complete"]').exists()).toBe(false)
  })

  it('shows a placeholder without a summary', () => {
    const wrapper = mountCell(BoughtItemDemandAllocationCell, { demandId: 1, status: 'open' })

    expect(wrapper.find('.alloc-cell').exists()).toBe(false)
    expect(wrapper.find('.muted').exists()).toBe(true)
  })
})

describe('BoughtItemDemandItemCell', () => {
  it('opens the item from its name and lists the substitutes', async () => {
    const wrapper = mountCell(
      BoughtItemDemandItemCell,
      { demand: makeDemandItemResponse({ item_id: 7 }) },
      makeSummary({
        substitutions: [
          {
            quantity: 2,
            substitute_item_id: 9,
            substitute_item_article_name: 'Wide Bolt',
            substitute_item_order_code_1: 'OC-9',
            substitute_reason: null,
          },
        ],
      }),
    )

    expect(wrapper.text()).toContain('Hex Bolt')
    expect(wrapper.find('.subst-label').text()).toBe('Wide Bolt - OC-9')

    await wrapper.find('.item-link').trigger('click')
    expect(wrapper.emitted('openItem')).toEqual([[7]])
  })
})

describe('BoughtItemDemandOrderCell', () => {
  it('shows a tag per order, each opening its order', async () => {
    const wrapper = mountCell(
      BoughtItemDemandOrderCell,
      { demandId: 1, quoteRequests: undefined },
      makeSummary({ order_ids: [3, 4], order_numbers: ['O-3'] }),
    )

    const tags = wrapper.findAll('.order-tag')
    expect(tags.map((tag) => tag.text())).toEqual(['O-3', '#4'])

    await tags[1]!.trigger('click')
    expect(wrapper.emitted('openOrder')).toEqual([[4]])
  })

  it('shows a placeholder without orders or quote requests', () => {
    const wrapper = mountCell(BoughtItemDemandOrderCell, { demandId: 1, quoteRequests: undefined })

    expect(wrapper.find('.order-tags').exists()).toBe(false)
    expect(wrapper.find('.muted').exists()).toBe(true)
  })
})
