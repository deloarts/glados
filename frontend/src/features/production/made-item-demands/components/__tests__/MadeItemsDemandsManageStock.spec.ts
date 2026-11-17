import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeMadeItemDemandResponse } from '@/test-utils/factories'
import { useMadeItemsProcurementStore } from '../../stores/madeItemsProcurementStore'

const post = vi.fn<() => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    post: () => post(),
  },
}))

import MadeItemsDemandsManageStock from '../MadeItemsDemandsManageStock.vue'

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(MadeItemsDemandsManageStock, {
    pinia,
    global: {
      stubs: { RouterLink: true },
    },
  })
  return {
    wrapper,
    procurementStore: useMadeItemsProcurementStore(),
  }
}

describe('MadeItemsDemandsManageStock', () => {
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
      makeMadeItemDemandResponse({ id: 1, quantity: 5 }),
      makeMadeItemDemandResponse({ id: 2, quantity: 3 }),
    ]
    await flushPromises()

    const rows = wrapper.findAll('.row-card')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.text()).toContain('Bracket')
  })

  it('removing a row drops it from the selection', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [makeMadeItemDemandResponse({ id: 1, quantity: 5 })]
    await flushPromises()

    await wrapper.get('.row-card button').trigger('click')
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(0)
    expect(wrapper.findAll('.row-card')).toHaveLength(0)
  })

  it('clears the selection and refreshes after a successful fulfill', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [makeMadeItemDemandResponse({ id: 1, quantity: 5 })]
    await flushPromises()

    const before = procurementStore.refreshTrigger
    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenCalled()
    expect(procurementStore.selectedDemands).toHaveLength(0)
    expect(procurementStore.refreshTrigger).toBe(before + 1)
  })
})
