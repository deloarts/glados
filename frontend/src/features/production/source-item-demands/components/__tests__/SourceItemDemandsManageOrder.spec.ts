import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeSourceItemDemandResponse } from '@/test-utils/factories'
import { useSourceItemDemandsSelectionStore } from '../../stores/sourceItemDemandsSelectionStore'

import type { OrderResponse } from '@/features/orders'

const draftOrder: OrderResponse = {
  edit_version: 0,
  id: 10,
  public_id: 'dddddddd-0000-0000-0000-000000000010',
  order_number: 'ORD-10',
  status: 'draft',
  created: '2026-01-01T00:00:00Z',
  changed: null,
  changed_by: null,
  changed_by_id: null,
  supplier_archived: false,
  extra_costs: [],
  quote_requests: [],
  lines_total: null,
  extra_costs_total: 0,
  net_total: null,
  note: null,
  ordered_date: null,
  expected_delivery_date: null,
  delivery_date: null,
  storage_place: null,
  creator_id: 1,
  creator: null,
  supplier_id: 5,
  supplier_name: 'Acme Supplies',
  supplier_vat_id: '',
  items: [],
  actions: [],
  blocked_actions: {},
  canceled_at: null,
  requested_at: null,
}

const substituteSourceItem: SourceItemResponse = {
  edit_version: 0,
  over_delivery_tolerance_percent: null,
  under_delivery_tolerance_percent: null,
  id: 2,
  public_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
  status: 'active',
  archived: false,
  created: '2026-01-01',
  changed: '2026-01-01T00:00:00Z',
  changed_by: null,
  changed_by_id: null,
  type_id: 1,
  type_name: { enGB: 'Rod' },
  dimension: '12mm',
  material: 'Steel',
  mass: 120,
  note: null,
  order_code_1: 'RB-12',
  order_code_2: null,
  successor_item_id: null,
  creator_id: 1,
  creator: null,
  approver_id: null,
  manufacturer_id: null,
  manufacturer_name: '',
}

// URL-dispatching get/post so this single mock can serve every endpoint the
// panel touches: draft orders (getOrders), the source-item search inside
// SourceItemSelect (rendered for every source-sourced row), and suppliers
// (loaded unconditionally on mount) for GET; order-item creation and
// allocation creation for POST.
let nextOrderItemId = 100
let postShouldFail = false

const getMock = vi.fn<(url: string) => Promise<unknown>>().mockImplementation((url: string) => {
  if (url === '/orders/') {
    return Promise.resolve({
      data: { items: [draftOrder], total: 1, limit: 200, skip: 0 },
    })
  }
  if (url === '/source-items') {
    return Promise.resolve({
      data: { items: [substituteSourceItem], total: 1, limit: 20, skip: 0 },
    })
  }
  return Promise.resolve({ data: { items: [], total: 0, limit: 0, skip: 0 } })
})

const postMock = vi
  .fn<(url: string, body: unknown) => Promise<unknown>>()
  .mockImplementation((url: string, body: unknown) => {
    if (postShouldFail) {
      return Promise.reject({
        response: { data: { detail: 'Something broke' } },
        isAxiosError: true,
      })
    }
    if (/^\/orders\/\d+\/items$/.test(url)) {
      const payload = body as { quantity: number }
      return Promise.resolve({
        data: { id: nextOrderItemId++, quantity: payload.quantity, ...(body as object) },
      })
    }
    if (url === '/source-item-allocations/') {
      return Promise.resolve({ data: { ...(body as object), source: 'order' } })
    }
    return Promise.resolve({ data: {} })
  })

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: (url: string, body: unknown) => postMock(url, body),
  },
}))

import SourceItemDemandsManageOrder from '../SourceItemDemandsManageOrder.vue'
import { SourceItemSelect } from '@/features/source-items'
import type { SourceItemDemandResponse, SourceItemResponse } from '@/features/source-items'

function makeBoughtDemand(
  overrides: Partial<SourceItemDemandResponse> = {},
): SourceItemDemandResponse {
  return makeSourceItemDemandResponse({
    source_item_id: null,
    source_item: null,
    bought_item_id: 7,
    bought_item: {
      id: 7,
      public_id: '77777777-7777-7777-7777-777777777777',
      status: 'active',
      article_name: 'Bolt M6',
      order_code_1: 'BLT-6',
      manufacturer_name: 'Acme',
    } as unknown as SourceItemDemandResponse['bought_item'],
    ...overrides,
  })
}

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(SourceItemDemandsManageOrder, {
    pinia,
    global: {
      stubs: { RouterLink: true },
    },
  })
  return {
    wrapper,
    selectionStore: useSourceItemDemandsSelectionStore(),
  }
}

async function selectDraftOrder(wrapper: ReturnType<typeof mountPanel>['wrapper']): Promise<void> {
  const orderSelect = wrapper.get('.order-select-row').findComponent({ name: 'Select' })
  orderSelect.vm.$emit('update:modelValue', draftOrder)
  await flushPromises()
}

describe('SourceItemDemandsManageOrder', () => {
  beforeEach(() => {
    getMock.mockClear()
    postMock.mockClear()
    postShouldFail = false
    nextOrderItemId = 100
  })

  it('shows the empty state with nothing selected', () => {
    const { wrapper } = mountPanel()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.find('.row-card').exists()).toBe(false)
  })

  it('builds one row per distinct material/unit/project', async () => {
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.selectedDemands = [
      makeSourceItemDemandResponse({ id: 1, quantity: 5 }),
      makeSourceItemDemandResponse({
        id: 2,
        quantity: 3,
        source_item_id: 2,
        source_item: null,
        unit: 'PCS',
      }),
    ]
    await flushPromises()

    expect(wrapper.findAll('.row-card')).toHaveLength(2)
  })

  it('shows the substitute section only on source-sourced rows', async () => {
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.selectedDemands = [
      makeSourceItemDemandResponse({ id: 1 }),
      makeBoughtDemand({ id: 2 }),
    ]
    await flushPromises()

    const rows = wrapper.findAll('.row-card')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.find('.substitute-section').exists()).toBe(true)
    expect(rows[1]!.find('.substitute-section').exists()).toBe(false)
  })

  it('submits a source-sourced row without a substitute using the demand material, its share on the line and no substitute reason', async () => {
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.selectedDemands = [makeSourceItemDemandResponse({ id: 1, source_item_id: 1 })]
    await flushPromises()

    await selectDraftOrder(wrapper)
    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    const itemCall = postMock.mock.calls.find(([url]) => /\/orders\/\d+\/items$/.test(url))
    expect(itemCall).toBeDefined()
    const itemBody = itemCall![1] as Record<string, unknown>
    expect(itemBody.source_item_id).toBe(1)
    expect(itemBody.bought_item_id).toBeUndefined()

    // The share travels with the line, so a refused share leaves no line.
    const shares = itemBody.source_demand_allocations as { demand_item_id: number }[]
    expect(shares.map((a) => a.demand_item_id)).toEqual([1])
    expect(itemBody.substitute_reason).toBeNull()
    expect(postMock.mock.calls.some(([url]) => url === '/source-item-allocations/')).toBe(false)
  })

  it('submits a source-sourced row with a chosen substitute using the substitute material and the trimmed reason on the line', async () => {
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.selectedDemands = [makeSourceItemDemandResponse({ id: 1, source_item_id: 1 })]
    await flushPromises()

    await wrapper
      .findComponent(SourceItemSelect)
      .vm.$emit('update:modelValue', substituteSourceItem)
    await flushPromises()

    const reasonInput = wrapper.find('.substitute-section input[type="text"]')
    expect(reasonInput.exists()).toBe(true)
    await reasonInput.setValue('  Preferred stock size  ')

    await selectDraftOrder(wrapper)
    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    const itemCall = postMock.mock.calls.find(([url]) => /\/orders\/\d+\/items$/.test(url))
    const itemBody = itemCall![1] as Record<string, unknown>
    expect(itemBody.source_item_id).toBe(2)

    // The backend records the substitution from the line's material.
    const shares = itemBody.source_demand_allocations as { demand_item_id: number }[]
    expect(shares.map((a) => a.demand_item_id)).toEqual([1])
    expect(itemBody.substitute_reason).toBe('Preferred stock size')
  })

  it('orders a demand separately on its own line with its own share', async () => {
    // Two demands of one material share a row; the second is ordered on its
    // own line, so each line names exactly the demand it is meant for.
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.selectedDemands = [
      makeSourceItemDemandResponse({ id: 1, source_item_id: 1, quantity: 5 }),
      makeSourceItemDemandResponse({ id: 2, source_item_id: 1, quantity: 3 }),
    ]
    await flushPromises()
    expect(wrapper.findAll('.row-card')).toHaveLength(1)

    const separate = wrapper
      .findAllComponents({ name: 'Button' })
      .filter((b) => b.props('label') === 'Order separately')
    await separate[1]!.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.row-card')).toHaveLength(2)

    await selectDraftOrder(wrapper)
    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    const lines = postMock.mock.calls
      .filter(([url]) => /\/orders\/\d+\/items$/.test(url))
      .map(([, body]) => body as { quantity: number; source_demand_allocations: unknown })
    expect(lines).toEqual([
      expect.objectContaining({
        quantity: 5,
        source_demand_allocations: [{ demand_item_id: 1, quantity: 5 }],
      }),
      expect.objectContaining({
        quantity: 3,
        source_demand_allocations: [{ demand_item_id: 2, quantity: 3 }],
      }),
    ])
  })

  it('submits a bought-sourced row with bought_item_id, not the old (broken) item_id key', async () => {
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.selectedDemands = [makeBoughtDemand({ id: 2 })]
    await flushPromises()

    await selectDraftOrder(wrapper)
    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    const itemCall = postMock.mock.calls.find(([url]) => /\/orders\/\d+\/items$/.test(url))
    expect(itemCall).toBeDefined()
    const itemBody = itemCall![1] as Record<string, unknown>
    expect(itemBody.bought_item_id).toBe(7)
    expect(itemBody.item_id).toBeUndefined()
    expect(itemBody.source_item_id).toBeUndefined()
  })

  it('clears the selection and bumps refreshTrigger after a successful submit', async () => {
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.selectedDemands = [makeSourceItemDemandResponse({ id: 1 })]
    await flushPromises()

    const before = selectionStore.refreshTrigger
    await selectDraftOrder(wrapper)
    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(selectionStore.selectedDemands).toHaveLength(0)
    expect(selectionStore.refreshTrigger).toBe(before + 1)
  })

  it('shows an error message when the API call fails', async () => {
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.selectedDemands = [makeSourceItemDemandResponse({ id: 1 })]
    await flushPromises()

    postShouldFail = true
    await selectDraftOrder(wrapper)
    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="manage-order-error"]').exists()).toBe(true)
  })
})
