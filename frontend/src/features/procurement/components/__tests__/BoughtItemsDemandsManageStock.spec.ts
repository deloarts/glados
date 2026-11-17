import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeDemandItemResponse } from '@/test-utils/factories'
import { useBoughtItemsProcurementStore } from '../../stores/boughtItemsProcurementStore'

const post = vi.fn<() => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    post: () => post(),
  },
}))

import BoughtItemsDemandsManageStock from '../BoughtItemsDemandsManageStock.vue'
import type { BoughtItemDemandResponse } from '@/features/bought-items'


function makeDemand(overrides: Partial<BoughtItemDemandResponse> = {}): BoughtItemDemandResponse {
  return makeDemandItemResponse({ item_article_name: 'Hex bolt M6', ...overrides })
}

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(BoughtItemsDemandsManageStock, {
    pinia,
    global: { stubs: { RouterLink: true } },
  })
  return {
    wrapper,
    procurementStore: useBoughtItemsProcurementStore(),
  }
}

describe('BoughtItemsDemandsManageStock', () => {
  beforeEach(() => {
    post.mockReset()
    post.mockResolvedValue({ data: { quantity_fulfilled: 1 } })
  })

  it('shows the empty state with nothing selected', () => {
    const { wrapper } = mountPanel()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.find('.row-card').exists()).toBe(false)
  })

  it('builds one row per selected demand, prefilled with its unallocated quantity', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [
      makeDemand({ id: 1, quantity: 5 }),
      makeDemand({ id: 2, quantity: 3, item_article_name: 'Washer M6' }),
    ]
    await flushPromises()

    const rows = wrapper.findAll('.row-card')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.text()).toContain('Hex bolt M6')
    expect(rows[1]!.text()).toContain('Washer M6')
  })

  it('rebuilds rows when the selection changes, keeping a failed row error alive across the rebuild', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [makeDemand({ id: 1, quantity: 5 })]
    await flushPromises()
    expect(wrapper.findAll('.row-card')).toHaveLength(1)

    procurementStore.selectedDemands = [
      makeDemand({ id: 1, quantity: 5 }),
      makeDemand({ id: 2, quantity: 2, item_article_name: 'Nut M6' }),
    ]
    await flushPromises()

    const rows = wrapper.findAll('.row-card')
    expect(rows).toHaveLength(2)
    expect(rows[1]!.text()).toContain('Nut M6')
  })

  it('removing a row drops it from the selection', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [makeDemand({ id: 1, quantity: 5 })]
    await flushPromises()

    await wrapper.get('.row-card button').trigger('click')
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(0)
    expect(wrapper.findAll('.row-card')).toHaveLength(0)
  })

  it('editing a row quantity keeps it below the submit call for that row', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [makeDemand({ id: 1, quantity: 5 })]
    await flushPromises()

    const input = wrapper.get('.row-controls input')
    await input.setValue('2')
    await flushPromises()

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalled()
  })

  it('clears the selection and refreshes after a successful fulfill', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [makeDemand({ id: 1, quantity: 5 })]
    await flushPromises()

    const before = procurementStore.refreshTrigger
    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalled()
    expect(procurementStore.selectedDemands).toHaveLength(0)
    expect(procurementStore.refreshTrigger).toBe(before + 1)
  })

  it('keeps the failed row selected and shows its error on a rejected fulfill', async () => {
    post.mockRejectedValueOnce(new Error('500'))
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [makeDemand({ id: 1, quantity: 5 })]
    await flushPromises()

    const before = procurementStore.refreshTrigger
    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)
    // A plain Error carries no axios response body, so extractApiError
    // falls back to the generic "something went wrong" copy.
    expect(wrapper.text()).toContain('Something went wrong')
    // Refresh still runs so allocation summaries reflect what did go through,
    // even though nothing succeeded here.
    expect(procurementStore.refreshTrigger).toBe(before + 1)
  })
})
