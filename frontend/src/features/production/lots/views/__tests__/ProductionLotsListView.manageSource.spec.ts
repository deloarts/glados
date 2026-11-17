import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { makeUserResponse } from '@/test-utils/factories'
import { useProductionLotsSourceStore } from '../../stores/productionLotsSourceStore'
import { useProductionLotsFiltersStore } from '../../stores/productionLotsFiltersStore'
import { useProductionLotsEditStore } from '../../stores/productionLotsEditStore'

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
  routes: [{ path: '/', component: { template: '<div />' } }],
})

let activeWrapper: { unmount: () => void } | null = null

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse({ is_systemuser: true })
  useProductionLotsFiltersStore().widescreenMode = true
  const wrapper = mountWithApp(ProductionLotsListView, {
    pinia,
    attachTo: document.body,
    global: {
      plugins: [router, ConfirmationService],
      stubs: { RouterLink: true },
    },
  })
  activeWrapper = wrapper
  return {
    wrapper,
    sourceStore: useProductionLotsSourceStore(),
    editStore: useProductionLotsEditStore(),
  }
}

function findButtonByText(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.text() === text)
}

async function openManageSource(wrapper: ReturnType<typeof mount>): Promise<void> {
  const button = findButtonByText(wrapper, 'Manage Source')
  await button!.trigger('click')
  await flushPromises()
}

async function openManageOrders(wrapper: ReturnType<typeof mount>): Promise<void> {
  const button = findButtonByText(wrapper, 'Manage Orders')
  await button!.trigger('click')
  await flushPromises()
}

describe('ProductionLotsListView Manage Source panel', () => {
  beforeEach(() => {
    getMock.mockReset()
    getMock.mockResolvedValue({ data: { items: [], total: 0, limit: 25, skip: 0 } })
  })

  afterEach(() => {
    activeWrapper?.unmount()
    activeWrapper = null
    document.body.innerHTML = ''
  })

  it('opens the Manage Source panel and fetches with actionable_for=source', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    getMock.mockClear()

    await openManageSource(wrapper)

    expect(wrapper.findComponent({ name: 'LotsListManageSourcePanel' }).exists()).toBe(true)
    const lotsCall = getMock.mock.calls.find(([url]) => url === '/production-lots/')
    expect(lotsCall?.[1]?.params).toMatchObject({ actionable_for: 'source' })
  })

  it('is mutually exclusive with Manage Orders', async () => {
    const { wrapper } = mountView()
    await flushPromises()

    await openManageSource(wrapper)
    expect(wrapper.findComponent({ name: 'LotsListManageSourcePanel' }).exists()).toBe(true)

    await openManageOrders(wrapper)
    expect(wrapper.findComponent({ name: 'LotsListManageSourcePanel' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'LotsListManageOrdersPanel' }).exists()).toBe(true)
  })

  it('clears the source selection when the panel is toggled closed', async () => {
    const { wrapper, sourceStore } = mountView()
    await flushPromises()

    await openManageSource(wrapper)
    sourceStore.setSelectedLots([
      {
        edit_version: 0,
        id: 1,
        public_id: '11111111-1111-1111-1111-111111111111',
        lot_number: 'LOT-1',
        quantity: 1,
        quantity_completed: 0,
        status: 'draft',
        priority: 'normal',
        created: '2026-07-01',
        changed: null,
        changed_by: null,
        changed_by_id: null,
        required_delivery_date: null,
        made_item_id: 1,
        made_item_part_number: 'PN-1',
        made_item_article_name: 'Bracket',
        made_item_revision: 'A',
        made_item_material: '1.0037',
        source_bought_item_id: null,
        source_item_id: null,
        source_made_item_id: null,
        source_label: '',
        source_sublabel: '',
        source_material: '',
        demand_status: '',
        is_alteration: false,
        project_id: 1,
        project_number: 'P-001',
        project_customer: 'Acme',
        creator_id: 1,
        creator: null,
        input_demand_id: null,
        source_approval_status: 'not_required',
        steps: [],
        positions: [],
        actions: [],
        blocked_actions: {},
        completed_at: null,
        origin_disposition: null,
        origin_lot_id: null,
        source_approved_by_id: null,
        source_approved_date: null,
        source_delivery_date: null,
        source_expected_delivery_date: null,
        source_order_id: null,
        source_order_number: null,
        source_rejected_by_id: null,
        source_rejected_date: null,
        source_rejection_reason: null,
        target_date: null,
        target_date_demand_item_id: null,
        target_date_source: null,
      },
    ])
    expect(sourceStore.selectedLots).toHaveLength(1)

    await openManageSource(wrapper)
    expect(sourceStore.selectedLots).toHaveLength(0)
  })

  it('closes when bulk edit mode is entered', async () => {
    const { wrapper, editStore } = mountView()
    await flushPromises()

    await openManageSource(wrapper)
    expect(wrapper.findComponent({ name: 'LotsListManageSourcePanel' }).exists()).toBe(true)

    editStore.toggleEditMode()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'LotsListManageSourcePanel' }).exists()).toBe(false)
  })
})
