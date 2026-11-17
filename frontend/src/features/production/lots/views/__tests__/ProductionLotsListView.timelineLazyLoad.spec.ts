import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { makeUserResponse } from '@/test-utils/factories'
import { useLotDetail } from '@/shared/composables/useLotDetail'

// The @svar-ui/vue-gantt chain LotsTimelineView pulls in only ships to
// users who actually open /production/lots/timeline. ProductionLotsListView
// wraps it in defineAsyncComponent (mirroring ProductionView.vue's
// asyncTab / AppLayout.vue's LotDetailDialog pattern). This spec proves the
// chunk boundary itself, not the gantt-task-building logic (that's
// lotsGanttTasks' own job).

// One lot with a single external (no production-order fetch needed)
// position, resolvable straight from expected_delivery_date, enough for
// buildLotGanttTasks to emit a non-empty task list, so the timeline renders
// AppGanttChart rather than its empty-state.
const FULL_LOT = {
  id: 1,
  lot_number: 'LOT-1',
  made_item_part_number: 'PN-1',
  status: 'in_progress',
  steps: [{ id: 10, position_id: 100, role: 'fabrication', fabrication_method_name: 'Milling' }],
  positions: [{ id: 100, kind: 'external', expected_delivery_date: '2026-08-01T00:00:00Z' }],
}

const getMock =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => getMock(url, config),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import ProductionLotsListView from '../ProductionLotsListView.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/production/lots', name: 'ProductionLots', component: { template: '<div />' } },
    {
      path: '/production/lots/timeline',
      name: 'ProductionLotsTimeline',
      component: { template: '<div />' },
    },
  ],
})

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse({ is_systemuser: true })

  return mountWithApp(ProductionLotsListView, {
    pinia,
    global: {
      plugins: [router, ConfirmationService],
      stubs: {
        RouterLink: true,
        // Out of scope for this spec; only LotsTimelineView's own lazy
        // loading is under test here.
        LotsControls: true,
        LotsViews: true,
        LotsTable: true,
        LotsListManageOrdersPanel: true,
        LotsListManageProductionPanel: true,
        LotsListManageSourcePanel: true,
        LotsEditPanel: true,
        LotForceStatusConfirmDialog: true,
        LotEditStepsDialog: true,
        SourceItemDemandCreateDialog: true,
        LotMaterialSourceDialog: true,
        MadeItemDetailDialog: true,
        ConfirmDialog: true,
        // AppGanttChart wraps the real @svar-ui widget, stubbed so this
        // spec exercises the chunk boundary without needing a full DOM
        // gantt render.
        AppGanttChart: true,
      },
    },
  })
}

describe('ProductionLotsListView, LotsTimelineView lazy loading', () => {
  beforeEach(async () => {
    getMock.mockReset()
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({ data: { items: [{ id: 1 }], total: 1, limit: 50, skip: 0 } })
      }
      if (url === '/production-lots/1') {
        return Promise.resolve({ data: FULL_LOT })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })
    useLotDetail().visible.value = false
    useLotDetail().lotId.value = null
  })

  it('does not mount LotsTimelineView synchronously when the timeline route is opened', async () => {
    await router.push({ name: 'ProductionLotsTimeline' })
    const wrapper = mountView()

    // No flushPromises/waitFor here on purpose: the dynamic import needs
    // real macrotasks to resolve, so an unresolved chunk must show neither
    // the view nor the chart synchronously.
    expect(wrapper.findComponent({ name: 'LotsTimelineView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'AppGanttChart' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('resolves LotsTimelineView once the chunk loads, mounting AppGanttChart', async () => {
    await router.push({ name: 'ProductionLotsTimeline' })
    const wrapper = mountView()

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'LotsTimelineView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    await flushPromises()

    expect(wrapper.findComponent({ name: 'AppGanttChart' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it('does not mount LotsTimelineView on the plain lots list route', async () => {
    await router.push({ name: 'ProductionLots' })
    const wrapper = mountView()
    await flushPromises()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'LotsTimelineView' }).exists()).toBe(false)

    wrapper.unmount()
  })
})
