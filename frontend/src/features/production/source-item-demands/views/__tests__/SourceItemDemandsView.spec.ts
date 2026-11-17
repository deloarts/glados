import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { Permission } from '@/core/auth/permissions'
import { useSourceItemDemandsFiltersStore } from '../../stores/sourceItemDemandsFiltersStore'

let hasPermissionMock = (_permission: string) => true
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => hasPermissionMock(permission) }),
}))

import SourceItemDemandsView from '../SourceItemDemandsView.vue'

const mounted: VueWrapper[] = []

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(SourceItemDemandsView, {
    global: {
      plugins: [pinia, i18n],
      stubs: {
        // Each owns its own store/api calls (fetch, allocations, order
        // creation), out of scope for this view, which only owns the page
        // shell, which manage panel is shown, and the resize handle.
        SourceItemDemandsControls: true,
        SourceItemDemandsViews: true,
        SourceItemDemandsTable: true,
        SourceItemDemandsManageOrder: true,
        SourceItemDemandsManageStock: true,
      },
    },
  })
  mounted.push(wrapper)
  return wrapper
}

describe('SourceItemDemandsView', () => {
  beforeEach(() => {
    hasPermissionMock = () => true
  })

  afterEach(() => {
    for (const wrapper of mounted) wrapper.unmount()
    mounted.length = 0
  })

  // This view has no fetch of its own: SourceItemDemandsTable (stubbed
  // above) owns the load entirely.

  it('shows neither manage panel by default', () => {
    const wrapper = mountView()

    expect(wrapper.findComponent({ name: 'SourceItemDemandsManageOrder' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'SourceItemDemandsManageStock' }).exists()).toBe(false)
    expect(wrapper.find('.resize-handle-ew').exists()).toBe(false)
  })

  it('shows the Manage Order panel once opened, with WRITE_ORDERS', async () => {
    const wrapper = mountView()
    useSourceItemDemandsFiltersStore().openPanel('orders')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'SourceItemDemandsManageOrder' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'SourceItemDemandsManageStock' }).exists()).toBe(false)
    expect(wrapper.find('.resize-handle-ew').exists()).toBe(true)
  })

  it('hides the Manage Order panel without WRITE_ORDERS, even when the filter store asks for it', async () => {
    hasPermissionMock = (permission) => permission !== Permission.WRITE_ORDERS

    const wrapper = mountView()
    useSourceItemDemandsFiltersStore().openPanel('orders')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'SourceItemDemandsManageOrder' }).exists()).toBe(false)
    expect(wrapper.find('.resize-handle-ew').exists()).toBe(false)
  })

  it('shows the Manage Stock panel once opened, with WRITE_ALLOCATIONS', async () => {
    const wrapper = mountView()
    useSourceItemDemandsFiltersStore().openPanel('stock')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'SourceItemDemandsManageStock' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'SourceItemDemandsManageOrder' }).exists()).toBe(false)
  })

  it('hides the Manage Stock panel without WRITE_ALLOCATIONS', async () => {
    hasPermissionMock = (permission) => permission !== Permission.WRITE_ALLOCATIONS

    const wrapper = mountView()
    useSourceItemDemandsFiltersStore().openPanel('stock')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'SourceItemDemandsManageStock' }).exists()).toBe(false)
  })

  it('widens the open manage panel by dragging the resize handle', async () => {
    const wrapper = mountView()
    useSourceItemDemandsFiltersStore().openPanel('orders')
    await flushPromises()

    const handle = wrapper.find('.resize-handle-ew')
    await handle.trigger('mousedown', { clientX: 100 })
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 160 }))
    await flushPromises()

    expect(
      wrapper.findComponent({ name: 'SourceItemDemandsManageOrder' }).attributes('style'),
    ).toContain('width: 420px')

    window.dispatchEvent(new MouseEvent('mouseup'))
  })
})
