import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { Permission } from '@/core/auth/permissions'
import { useMadeItemsDemandsFiltersStore } from '../../stores/madeItemsDemandsFiltersStore'

import MadeItemDemandsView from '../MadeItemDemandsView.vue'

function mountView(permissions: string[] = [], productionPlanningEnabled = true) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  useHostStore().productionPlanningEnabled = productionPlanningEnabled

  const wrapper = mountWithApp(MadeItemDemandsView, {
    pinia,
    global: {
      stubs: {
        MadeItemsDemandsControls: true,
        MadeItemsDemandsViews: true,
        MadeItemsDemandsTable: true,
        MadeItemsDemandsManageLots: true,
        MadeItemsDemandsManageStock: true,
      },
    },
  })
  return { pinia, wrapper }
}

describe('MadeItemDemandsView', () => {
  it('renders the demands table', () => {
    const { wrapper } = mountView()

    expect(wrapper.findComponent({ name: 'PageLayout' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'MadeItemsDemandsTable' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it('shows neither manage panel by default', () => {
    const { wrapper } = mountView([Permission.WRITE_LOTS, Permission.WRITE_ALLOCATIONS])

    expect(wrapper.findComponent({ name: 'MadeItemsDemandsManageLots' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'MadeItemsDemandsManageStock' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('shows the manage-lots panel only with write:lots and production planning enabled', async () => {
    const { pinia, wrapper } = mountView([])
    setActivePinia(pinia)
    useMadeItemsDemandsFiltersStore().openPanel('lots')
    await wrapper.vm.$nextTick()
    expect(wrapper.findComponent({ name: 'MadeItemsDemandsManageLots' }).exists()).toBe(false)
    wrapper.unmount()

    const { pinia: pinia2, wrapper: wrapper2 } = mountView([Permission.WRITE_LOTS], false)
    setActivePinia(pinia2)
    useMadeItemsDemandsFiltersStore().openPanel('lots')
    await wrapper2.vm.$nextTick()
    expect(wrapper2.findComponent({ name: 'MadeItemsDemandsManageLots' }).exists()).toBe(false)
    wrapper2.unmount()

    const { pinia: pinia3, wrapper: wrapper3 } = mountView([Permission.WRITE_LOTS], true)
    setActivePinia(pinia3)
    useMadeItemsDemandsFiltersStore().openPanel('lots')
    await wrapper3.vm.$nextTick()
    expect(wrapper3.findComponent({ name: 'MadeItemsDemandsManageLots' }).exists()).toBe(true)
    wrapper3.unmount()
  })

  it('shows the manage-stock panel only with write:allocations, regardless of production planning', async () => {
    const { pinia, wrapper } = mountView([], false)
    setActivePinia(pinia)
    useMadeItemsDemandsFiltersStore().openPanel('stock')
    await wrapper.vm.$nextTick()
    expect(wrapper.findComponent({ name: 'MadeItemsDemandsManageStock' }).exists()).toBe(false)
    wrapper.unmount()

    const { pinia: pinia2, wrapper: wrapper2 } = mountView([Permission.WRITE_ALLOCATIONS], false)
    setActivePinia(pinia2)
    useMadeItemsDemandsFiltersStore().openPanel('stock')
    await wrapper2.vm.$nextTick()
    expect(wrapper2.findComponent({ name: 'MadeItemsDemandsManageStock' }).exists()).toBe(true)
    wrapper2.unmount()
  })

  it('prefers the manage-lots panel over manage-stock when both flags are somehow set', async () => {
    const { pinia, wrapper } = mountView(
      [Permission.WRITE_LOTS, Permission.WRITE_ALLOCATIONS],
      true,
    )
    setActivePinia(pinia)
    const filters = useMadeItemsDemandsFiltersStore()
    filters.openPanel('lots')
    filters.showManageStockPanel = true
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'MadeItemsDemandsManageLots' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'MadeItemsDemandsManageStock' }).exists()).toBe(false)

    wrapper.unmount()
  })
})
