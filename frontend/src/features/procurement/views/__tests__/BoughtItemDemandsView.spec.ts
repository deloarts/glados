import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'
import { useBoughtItemsDemandsFiltersStore } from '../../stores/boughtItemsDemandsFiltersStore'

import BoughtItemDemandsView from '../BoughtItemDemandsView.vue'

function mountView(permissions: string[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  const wrapper = mountWithApp(BoughtItemDemandsView, {
    pinia,
    global: {
      stubs: {
        BoughtItemsDemandsControls: true,
        BoughtItemsDemandsViews: true,
        BoughtItemsDemandsTable: true,
        BoughtItemsDemandsManageOrder: true,
        BoughtItemsDemandsManageStock: true,
      },
    },
  })
  return { pinia, wrapper }
}

describe('BoughtItemDemandsView', () => {
  it('renders the demands table', () => {
    const { wrapper } = mountView()

    expect(wrapper.findComponent({ name: 'PageLayout' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'BoughtItemsDemandsTable' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it('shows neither manage panel by default', () => {
    const { wrapper } = mountView([Permission.WRITE_ORDERS, Permission.WRITE_ALLOCATIONS])

    expect(wrapper.findComponent({ name: 'BoughtItemsDemandsManageOrder' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'BoughtItemsDemandsManageStock' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('shows the manage-order panel only with write:orders, even when the filters store asks for it', async () => {
    const { pinia, wrapper } = mountView([])
    setActivePinia(pinia)
    useBoughtItemsDemandsFiltersStore().openPanel('orders')
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'BoughtItemsDemandsManageOrder' }).exists()).toBe(false)
    wrapper.unmount()

    const { pinia: pinia2, wrapper: wrapper2 } = mountView([Permission.WRITE_ORDERS])
    setActivePinia(pinia2)
    useBoughtItemsDemandsFiltersStore().openPanel('orders')
    await wrapper2.vm.$nextTick()

    expect(wrapper2.findComponent({ name: 'BoughtItemsDemandsManageOrder' }).exists()).toBe(true)
    wrapper2.unmount()
  })

  it('shows the manage-stock panel only with write:allocations, even when the filters store asks for it', async () => {
    const { pinia, wrapper } = mountView([])
    setActivePinia(pinia)
    useBoughtItemsDemandsFiltersStore().openPanel('stock')
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'BoughtItemsDemandsManageStock' }).exists()).toBe(false)
    wrapper.unmount()

    const { pinia: pinia2, wrapper: wrapper2 } = mountView([Permission.WRITE_ALLOCATIONS])
    setActivePinia(pinia2)
    useBoughtItemsDemandsFiltersStore().openPanel('stock')
    await wrapper2.vm.$nextTick()

    expect(wrapper2.findComponent({ name: 'BoughtItemsDemandsManageStock' }).exists()).toBe(true)
    wrapper2.unmount()
  })

  it('prefers the manage-order panel over manage-stock when both flags are somehow set', async () => {
    const { pinia, wrapper } = mountView([Permission.WRITE_ORDERS, Permission.WRITE_ALLOCATIONS])
    setActivePinia(pinia)
    const filters = useBoughtItemsDemandsFiltersStore()
    filters.openPanel('orders')
    filters.showManageStockPanel = true
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'BoughtItemsDemandsManageOrder' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'BoughtItemsDemandsManageStock' }).exists()).toBe(false)

    wrapper.unmount()
  })
})
