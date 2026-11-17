import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

import { useProductionLotsSelectionStore } from '../../stores/productionLotsSelectionStore'
import { useProductionLotsFiltersStore } from '../../stores/productionLotsFiltersStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLoadingBarStore } from '@/core/stores/loadingBarStore'
import { makeUserResponse } from '@/test-utils/factories'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { useProductionLotsEditStore } from '../../stores/productionLotsEditStore'

import type { LotResponse, LotSummaryResponse } from '../../../types/productionLotsResponse'

function makeSummaryLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    lot_number: 'LOT-1',
    quantity: 10,
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
    steps: [
      {
        id: 1,
        public_id: '11111111-1111-1111-1111-111111111111',
        created: '2026-07-01',
        note: null,
        estimated_setup_minutes: null,
        estimated_minutes_per_piece: null,
        time_budget_per_piece: null,
        sequence: 1,
        creator_id: 1,
        fabrication_method_id: 1,
        role: 'fabrication' as const,
        inspection_method_id: null,
        inspection_method_name: null,
        inspection_method_requires_evidence: null,
        fabrication_method_name: { enGB: 'Milling' },
        fabrication_method_requires_machine: true,
        fabrication_method_required_external: false,
        fabrication_method_default_supplier_id: null,
        lot_id: 1,
        position_id: 1,
        source_process_id: null,
        position_kind: 'unassigned',
        // An unassigned position with quantity left offers both assignments.
        actions: ['assign_external', 'assign_internal'],
        position_needs_machine: false,
        position_status: 'pending',
        position_quantity: 10,
        position_quantity_remaining: 10,
      },
      {
        id: 2,
        public_id: '22222222-2222-2222-2222-222222222222',
        created: '2026-07-01',
        note: null,
        estimated_setup_minutes: null,
        estimated_minutes_per_piece: null,
        time_budget_per_piece: null,
        sequence: 2,
        creator_id: 1,
        fabrication_method_id: 1,
        role: 'fabrication' as const,
        inspection_method_id: null,
        inspection_method_name: null,
        inspection_method_requires_evidence: null,
        fabrication_method_name: { enGB: 'Turning' },
        fabrication_method_requires_machine: true,
        fabrication_method_required_external: false,
        fabrication_method_default_supplier_id: null,
        lot_id: 1,
        position_id: 2,
        source_process_id: null,
        position_kind: 'external',
        position_needs_machine: false,
        position_status: 'pending',
        position_quantity: 10,
        position_quantity_remaining: 0,
        actions: [],
      },
    ],
    // One per distinct step position. Rides along on the list response
    // (LotSummaryPositionResponse) instead of being fetched per lot.
    positions: [1, 2].map((positionId) => ({
      id: positionId,
      kind: 'unassigned' as const,
      order_id: null,
      order_number: '',
      order_item_id: null,
      order_item_status: '',
      order_item_closed_short: false,
      order_item_quantity: null,
      order_item_quantity_delivered: null,
      order_item_unit: '',
      order_item_items_per_unit: 1,
      order_item_edit_version: 0,
      expected_delivery_date: null,
      delivery_date: null,
      expected_pickup_date: null,
      ready_for_pickup_date: null,
      delivery_record_count: 0,
      ordered_by_name: null,
      lead_days: null,
      lead_days_source: null,
      planned_delivery_date: null,
      planned_pickup_date: null,
      production_orders: [],
    })),
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
    ...overrides,
  }
}

// Two unassigned single-step positions: Milling (fabrication method 1) and
// Grinding (method 2). The fixture the Manage Production capability-filtering
// tests select a machine/pool against.
function makeCapabilityLot(): LotSummaryResponse {
  const base = { ...makeSummaryLot().steps![0]!, position_quantity_remaining: 10 }
  return makeSummaryLot({
    steps: [
      base,
      {
        ...base,
        id: 2,
        sequence: 2,
        fabrication_method_id: 2,
        role: 'fabrication' as const,
        inspection_method_id: null,
        inspection_method_name: null,
        inspection_method_requires_evidence: null,
        fabrication_method_name: { enGB: 'Grinding' },
        position_id: 2,
      },
    ],
  })
}

// Two steps sharing one position (Milling + Turning), the fixture the
// grouping-collapse tests assert renders as a single combined cell/chip.
function makeGroupedLot(): LotSummaryResponse {
  const base = { ...makeSummaryLot().steps![0]!, position_quantity_remaining: 10 }
  return makeSummaryLot({
    steps: [
      { ...base, id: 1, sequence: 1, position_id: 1, fabrication_method_name: { enGB: 'Milling' } },
      { ...base, id: 2, sequence: 2, position_id: 1, fabrication_method_name: { enGB: 'Turning' } },
    ],
    positions: [
      {
        id: 1,
        kind: 'unassigned' as const,
        order_id: null,
        order_number: '',
        order_item_id: null,
        order_item_status: '',
        order_item_closed_short: false,
        order_item_quantity: null,
        order_item_quantity_delivered: null,
        order_item_unit: '',
        order_item_items_per_unit: 1,
        order_item_edit_version: 0,
        expected_delivery_date: null,
        delivery_date: null,
        expected_pickup_date: null,
        ready_for_pickup_date: null,
        delivery_record_count: 0,
        ordered_by_name: null,
        production_orders: [],
        lead_days: null,
        lead_days_source: null,
        planned_delivery_date: null,
        planned_pickup_date: null,
      },
    ],
  })
}

function makeFullLot(overrides: Partial<LotResponse> = {}): LotResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '00000000-0000-0000-0000-000000000001',
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    lot_number: 'LOT-1',
    quantity: 10,
    quantity_completed: 0,
    status: 'draft',
    priority: 'normal',
    note: null,
    required_delivery_date: null,
    creator_id: 1,
    creator: null,
    made_item_id: 1,
    made_item_part_number: 'PN-1',
    source_bought_item_id: null,
    source_item_id: null,
    source_made_item_id: null,
    source_label: '',
    source_sublabel: '',
    demand_status: '',
    is_alteration: false,
    made_item_article_name: 'Bracket',
    made_item_revision: 'A',
    made_item_material: '1.0037',
    project_id: 1,
    project_number: 'P-001',
    project_customer: 'Acme',
    input_demand_id: null,
    source_approval_status: 'not_required',
    positions: [
      {
        id: 1,
        public_id: '00000203-0000-0000-0000-000000000000',
        created: '2026-07-01',
        changed: null,
        changed_by: null,
        changed_by_id: null,
        sequence: 1,
        kind: 'unassigned',
        status: 'pending',
        actions: ['assign_external', 'assign_internal'],
        quantity: 10,
        quantity_completed: 0,
        quantity_remaining: 10,
        note: null,
        creator_id: 1,
        lot_id: 1,
        steps: [],
        order_item_id: null,
        order_id: null,
        order_number: '',
        supplier_name: '',
        order_item_status: '',
        order_item_closed_short: false,
        earlier_order_lines: [],
        expected_delivery_date: null,
        production_orders: [],
        planned_delivery_date: null,
        planned_pickup_date: null,
      },
    ],
    steps: [],
    actions: [],
    blocked_actions: {},
    canceled_at: null,
    completed_at: null,
    follow_up_lots: [],
    force_completed_at: null,
    held_at: null,
    origin_disposition: null,
    origin_lot_id: null,
    origin_lot_number: null,
    source_approved_by_id: null,
    source_approved_date: null,
    source_delivery_date: null,
    source_expected_delivery_date: null,
    source_order_id: null,
    source_order_number: null,
    source_rejected_by_id: null,
    source_rejected_date: null,
    source_rejection_reason: null,
    ...overrides,
  }
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
  routes: [{ path: '/', component: { template: '<div />' } }],
})

function mountView(options: { simpleMode?: boolean } = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse({ is_systemuser: true })
  // These cover Simple and Widescreen Mode; Column Mode (the app default)
  // has its own spec, so opt out of it here.
  useProductionLotsFiltersStore().widescreenMode = true
  if (options.simpleMode) {
    useProductionLotsFiltersStore().simpleMode = true
  }
  const wrapper = mountWithApp(ProductionLotsListView, {
    pinia,
    attachTo: document.body,
    global: {
      plugins: [router, ConfirmationService],
      stubs: { RouterLink: true },
    },
  })
  return { wrapper, selectionStore: useProductionLotsSelectionStore() }
}

// Non-simple mode renders each step's method as a plain, non-Tag cell (see
// ProductionLotsListView.vue's step-method-cell) carrying a second "source"
// line, UNLESS a Manage panel is open and the step is currently selectable,
// in which case it renders as a real Button instead (no source line). Look
// it up by whichever shape matches the method text.
function findMethodButton(wrapper: ReturnType<typeof mount>, methodText: string) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === methodText)
}

function findMethodCell(wrapper: ReturnType<typeof mount>, methodText: string) {
  const button = findMethodButton(wrapper, methodText)
  if (button) return button
  return wrapper
    .findAll('.step-method-cell')
    .find((el) => el.find('.step-method-name').text() === methodText)
}

async function openManageOrders(wrapper: ReturnType<typeof mount>): Promise<void> {
  const buttons = wrapper.findAllComponents({ name: 'Button' })
  const manageOrdersButton = buttons.find((b) => b.text() === 'Manage Orders')
  await manageOrdersButton!.trigger('click')
  await flushPromises()
}

async function openManageProduction(wrapper: ReturnType<typeof mount>): Promise<void> {
  const buttons = wrapper.findAllComponents({ name: 'Button' })
  const manageProductionButton = buttons.find((b) => b.text() === 'Manage Production')
  await manageProductionButton!.trigger('click')
  await flushPromises()
}

async function openManageSource(wrapper: ReturnType<typeof mount>): Promise<void> {
  const buttons = wrapper.findAllComponents({ name: 'Button' })
  const manageSourceButton = buttons.find((b) => b.text() === 'Manage Source')
  await manageSourceButton!.trigger('click')
  await flushPromises()
}

describe('ProductionLotsListView step selection', () => {
  beforeEach(async () => {
    getMock.mockReset()
    await router.push('/')
    // useLotDetail() is a module-scope singleton (by design; see its own
    // file), so it survives across tests unless reset here.
    useLotDetail().visible.value = false
    useLotDetail().lotId.value = null
  })

  it('adds the position behind an unassigned step chip to the batch on click (Manage Orders)', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: { items: [makeSummaryLot()], total: 1, limit: 25, skip: 0 },
        })
      }
      if (url === '/production-lots/1') {
        return Promise.resolve({ data: makeFullLot() })
      }
      if (/^\/production-lots\/\d+$/.test(url)) {
        return Promise.resolve({ data: makeFullLot() })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const { wrapper, selectionStore } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageOrders(wrapper)

    const unassignedCell = findMethodCell(wrapper, 'Milling')
    expect(unassignedCell).toBeTruthy()
    await unassignedCell!.trigger('click')
    await flushPromises()

    expect(selectionStore.items).toHaveLength(1)
    expect(selectionStore.items[0]).toMatchObject({ lotId: 1, position: { id: 1 } })
    // Clicking a selectable step must not also trigger the row's own
    // open-lot-detail click handler (event.stopPropagation() in
    // onStepClick is what's relied on for this).
    expect(useLotDetail().visible.value).toBe(false)

    wrapper.unmount()
  })

  it('appends the allocated/needed quantity to a partially allocated step tag', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: {
            items: [
              makeSummaryLot({
                steps: [
                  {
                    public_id: '11111111-1111-1111-1111-111111111111',
                    id: 1,
                    created: '2026-07-01',
                    note: null,
                    estimated_setup_minutes: null,
                    estimated_minutes_per_piece: null,
                    time_budget_per_piece: null,
                    sequence: 1,
                    creator_id: 1,
                    fabrication_method_id: 1,
                    role: 'fabrication' as const,
                    inspection_method_id: null,
                    inspection_method_name: null,
                    inspection_method_requires_evidence: null,
                    fabrication_method_name: { enGB: 'Milling' },
                    fabrication_method_requires_machine: true,
                    fabrication_method_required_external: false,
                    fabrication_method_default_supplier_id: null,
                    lot_id: 1,
                    position_id: 1,
                    source_process_id: null,
                    position_kind: 'internal',
                    position_needs_machine: false,
                    position_status: 'in_progress',
                    position_quantity: 4,
                    position_quantity_remaining: 1,
                    actions: [],
                  },
                ],
              }),
            ],
            total: 1,
            limit: 25,
            skip: 0,
          },
        })
      }
      if (/^\/production-lots\/\d+$/.test(url)) {
        return Promise.resolve({ data: makeFullLot() })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    expect(findMethodCell(wrapper, 'Milling (3/4)')).toBeTruthy()

    wrapper.unmount()
  })

  it('does not add a step whose position is not unassigned while Manage Orders is open', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: { items: [makeSummaryLot()], total: 1, limit: 25, skip: 0 },
        })
      }
      if (/^\/production-lots\/\d+$/.test(url)) {
        return Promise.resolve({ data: makeFullLot() })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    // Simple Mode: non-simple mode's delivery-date column always fetches
    // every visible lot's full detail, which would make the "never
    // fetched" assertion below meaningless for an unrelated reason.
    const { wrapper, selectionStore } = mountView({ simpleMode: true })
    await flushPromises()
    await flushPromises()
    await openManageOrders(wrapper)

    const tags = wrapper.findAllComponents({ name: 'Tag' })
    const externalTag = tags.find((t) => t.text() === 'Turning')
    expect(externalTag).toBeTruthy()
    await externalTag!.trigger('click')
    await flushPromises()

    expect(selectionStore.items).toHaveLength(0)
    // The GET for /production-lots/1 (full detail) must never have fired.
    expect(getMock).not.toHaveBeenCalledWith('/production-lots/1')

    wrapper.unmount()
  })

  it('does not render a Button for a fully-planned internal step while Manage Orders is open', async () => {
    // An INTERNAL position can be fully queued already (quantity_remaining
    // 0), nothing left to top up externally, and assign_external_position.py
    // rejects exactly that server-side. isStepClickable therefore checks
    // remaining quantity as well as position_kind (unassigned/internal), so
    // such a step does not render as a clickable Button.
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: {
            items: [
              makeSummaryLot({
                steps: [
                  {
                    ...makeSummaryLot().steps![0]!,
                    fabrication_method_name: { enGB: 'Turning' },
                    position_kind: 'internal',
                    position_status: 'ordered_or_queued',
                    position_quantity: 48,
                    position_quantity_remaining: 0,
                    // Fully queued: nothing left to assign either way.
                    actions: [],
                  },
                ],
              }),
            ],
            total: 1,
            limit: 25,
            skip: 0,
          },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageOrders(wrapper)

    expect(findMethodButton(wrapper, 'Turning')).toBeFalsy()
    expect(findMethodCell(wrapper, 'Turning')).toBeTruthy()

    wrapper.unmount()
  })

  it('adds a step to the batch on click (Manage Production) without navigating to the lot detail', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: {
            items: [
              makeSummaryLot({
                steps: [
                  {
                    public_id: '11111111-1111-1111-1111-111111111111',
                    id: 1,
                    created: '2026-07-01',
                    note: null,
                    estimated_setup_minutes: null,
                    estimated_minutes_per_piece: null,
                    time_budget_per_piece: null,
                    sequence: 1,
                    creator_id: 1,
                    fabrication_method_id: 1,
                    role: 'fabrication' as const,
                    inspection_method_id: null,
                    inspection_method_name: null,
                    inspection_method_requires_evidence: null,
                    fabrication_method_name: { enGB: 'Milling' },
                    fabrication_method_requires_machine: true,
                    fabrication_method_required_external: false,
                    fabrication_method_default_supplier_id: null,
                    lot_id: 1,
                    position_id: 1,
                    source_process_id: null,
                    position_kind: 'unassigned',
        // An unassigned position with quantity left offers both assignments.
        actions: ['assign_external', 'assign_internal'],
                    position_needs_machine: false,
                    position_status: 'pending',
                    position_quantity: 10,
                    position_quantity_remaining: 10,
                  },
                ],
              }),
            ],
            total: 1,
            limit: 25,
            skip: 0,
          },
        })
      }
      if (/^\/production-lots\/\d+$/.test(url)) {
        return Promise.resolve({ data: makeFullLot() })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const { wrapper, selectionStore } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageProduction(wrapper)

    const unassignedCell = findMethodCell(wrapper, 'Milling')
    expect(unassignedCell).toBeTruthy()
    await unassignedCell!.trigger('click')
    await flushPromises()

    expect(selectionStore.items).toHaveLength(1)
    expect(selectionStore.items[0]).toMatchObject({ lotId: 1, position: { id: 1 } })
    // Same stopPropagation() concern as the other click-to-select tests.
    expect(useLotDetail().visible.value).toBe(false)

    wrapper.unmount()
  })

  it('clicking twice removes the step from the batch again', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: { items: [makeSummaryLot()], total: 1, limit: 25, skip: 0 },
        })
      }
      return Promise.resolve({ data: makeFullLot() })
    })

    const { wrapper, selectionStore } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageOrders(wrapper)

    const unassignedCell = findMethodCell(wrapper, 'Milling')
    await unassignedCell!.trigger('click')
    await flushPromises()
    expect(selectionStore.items).toHaveLength(1)

    await unassignedCell!.trigger('click')
    await flushPromises()
    expect(selectionStore.items).toHaveLength(0)

    wrapper.unmount()
  })

  it('bounces back and clears the batch when the position is no longer available', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: {
            items: [
              makeSummaryLot({
                steps: [
                  {
                    public_id: '33333333-3333-3333-3333-333333333333',
                    id: 3,
                    created: '2026-07-01',
                    note: null,
                    estimated_setup_minutes: null,
                    estimated_minutes_per_piece: null,
                    time_budget_per_piece: null,
                    sequence: 1,
                    creator_id: 1,
                    fabrication_method_id: 1,
                    role: 'fabrication' as const,
                    inspection_method_id: null,
                    inspection_method_name: null,
                    inspection_method_requires_evidence: null,
                    fabrication_method_name: { enGB: 'Drilling' },
                    fabrication_method_requires_machine: true,
                    fabrication_method_required_external: false,
                    fabrication_method_default_supplier_id: null,
                    lot_id: 1,
                    position_id: 1,
                    source_process_id: null,
                    position_kind: 'unassigned',
        // An unassigned position with quantity left offers both assignments.
        actions: ['assign_external', 'assign_internal'],
                    position_needs_machine: false,
                    position_status: 'pending',
                    position_quantity: 10,
                    position_quantity_remaining: 10,
                  },
                ],
              }),
            ],
            total: 1,
            limit: 25,
            skip: 0,
          },
        })
      }
      if (url === '/production-lots/1') {
        // Race: by the time the full lot loads, the position is already external.
        return Promise.resolve({
          data: makeFullLot({
            positions: [
              {
                id: 1,
                public_id: '00000202-0000-0000-0000-000000000000',
                created: '2026-07-01',
                changed: null,
                changed_by: null,
                changed_by_id: null,
                sequence: 1,
                kind: 'external',
                status: 'pending',
                quantity: 10,
                quantity_completed: 0,
                quantity_remaining: 0,
                note: null,
                creator_id: 1,
                lot_id: 1,
                steps: [],
                order_item_id: 5,
                order_id: 5,
                order_number: 'ORD-5',
                supplier_name: 'Acme',
                order_item_status: 'ordered',
                order_item_closed_short: false,
                earlier_order_lines: [],
                expected_delivery_date: null,
                production_orders: [],
                actions: [],
                planned_delivery_date: null,
                planned_pickup_date: null,
              },
            ],
          }),
        })
      }
      if (/^\/production-lots\/\d+$/.test(url)) {
        return Promise.resolve({ data: makeFullLot() })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const { wrapper, selectionStore } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageOrders(wrapper)

    const drillingCell = findMethodCell(wrapper, 'Drilling')
    expect(drillingCell).toBeTruthy()
    await drillingCell!.trigger('click')
    await flushPromises()
    await flushPromises()

    expect(selectionStore.items).toHaveLength(0)

    wrapper.unmount()
  })

  it('Manage Production: filters clickability by capability once a machine is selected', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: {
            items: [makeCapabilityLot()],
            total: 1,
            limit: 25,
            skip: 0,
          },
        })
      }
      if (url === '/production-machines/') {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 1,
                deleted: false,
                created: '2026-07-01',
                changed: null,
                internal_name: 'Mill A',
                vendor: 'Acme',
                model: 'M1',
                fabrication_method_ids: [1],
                fabrication_methods: [],
                max_part_dimension: null,
                note: null,
                is_qa_machine: false,
                creator_id: 1,
                creator_full_name: 'Tester',
                changes: [],
              },
            ],
            total: 1,
            limit: 200,
            skip: 0,
          },
        })
      }
      if (url === '/production-lots/1') {
        return Promise.resolve({
          data: makeFullLot({
            positions: [
              {
                id: 1,
                public_id: '00000201-0000-0000-0000-000000000000',
                created: '2026-07-01',
                changed: null,
                changed_by: null,
                changed_by_id: null,
                sequence: 1,
                kind: 'unassigned',
                status: 'pending',
                actions: ['assign_external', 'assign_internal'],
                quantity: 10,
                quantity_completed: 0,
                quantity_remaining: 10,
                note: null,
                creator_id: 1,
                lot_id: 1,
                steps: [
                  {
                    public_id: '11111111-1111-1111-1111-111111111111',
                    id: 1,
                    created: '2026-07-01',
                    note: null,
                    estimated_setup_minutes: null,
                    estimated_minutes_per_piece: null,
                    time_budget_per_piece: null,
                    sequence: 1,
                    creator_id: 1,
                    fabrication_method_id: 1,
                    role: 'fabrication' as const,
                    inspection_method_id: null,
                    inspection_method_name: null,
                    inspection_method_requires_evidence: null,
                    fabrication_method_name: { enGB: 'Milling' },
                    fabrication_method_requires_machine: true,
                    fabrication_method_required_external: false,
                    fabrication_method_default_supplier_id: null,
                    lot_id: 1,
                    position_id: 1,
                    source_process_id: null,
                  },
                ],
                order_item_id: null,
                order_id: null,
                order_number: '',
                supplier_name: '',
                order_item_status: '',
                order_item_closed_short: false,
                earlier_order_lines: [],
                expected_delivery_date: null,
                production_orders: [],
                planned_delivery_date: null,
                planned_pickup_date: null,
              },
            ],
          }),
        })
      }
      if (/^\/production-lots\/\d+$/.test(url)) {
        return Promise.resolve({ data: makeFullLot() })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const { wrapper, selectionStore } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageProduction(wrapper)
    await flushPromises()

    // No machine selected yet -> both unassigned steps are clickable
    // (rendered as real Buttons instead of plain cells).
    expect(findMethodButton(wrapper, 'Milling')).toBeTruthy()
    expect(findMethodButton(wrapper, 'Grinding')).toBeTruthy()

    const targetSelect = wrapper.find('.machine-section').findComponent({ name: 'Select' })
    await targetSelect.vm.$emit('update:modelValue', 'machine:1')
    await flushPromises()

    // Mill A only covers fabrication method 1 (Milling's), not Grinding's.
    expect(findMethodButton(wrapper, 'Milling')).toBeTruthy()
    expect(findMethodButton(wrapper, 'Grinding')).toBeFalsy()

    await findMethodButton(wrapper, 'Milling')!.trigger('click')
    await flushPromises()
    expect(selectionStore.items).toHaveLength(1)

    // Grinding is no longer clickable -> renders as a plain (non-Button) cell
    // with no click handler of its own; clicking it must not add anything.
    const grindingCell = findMethodCell(wrapper, 'Grinding')!
    await grindingCell.trigger('click')
    await flushPromises()
    expect(selectionStore.items).toHaveLength(1)

    wrapper.unmount()
  })

  it('Manage Production: filters clickability by capability once a pool is selected', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: { items: [makeCapabilityLot()], total: 1, limit: 25, skip: 0 },
        })
      }
      if (url === '/production-machine-pools/') {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 7,
                deleted: false,
                created: '2026-07-01',
                changed: null,
                name: 'Mill Pool',
                machine_ids: [1, 2],
                // Pool capability is the intersection: method 1 only.
                machines: [
                  { id: 1, internal_name: 'Mill A', fabrication_method_ids: [1, 2] },
                  { id: 2, internal_name: 'Mill B', fabrication_method_ids: [1] },
                ],
                note: null,
                creator_id: 1,
                creator_full_name: 'Tester',
                changes: [],
              },
            ],
            total: 1,
            limit: 1000,
            skip: 0,
          },
        })
      }
      if (/^\/production-lots\/\d+$/.test(url)) {
        return Promise.resolve({ data: makeFullLot() })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageProduction(wrapper)
    await flushPromises()

    expect(findMethodButton(wrapper, 'Milling')).toBeTruthy()
    expect(findMethodButton(wrapper, 'Grinding')).toBeTruthy()

    const targetSelect = wrapper.find('.machine-section').findComponent({ name: 'Select' })
    await targetSelect.vm.$emit('update:modelValue', 'pool:7')
    await flushPromises()

    // Not every machine in the pool can grind, so Grinding drops out exactly
    // as it does for a single incapable machine.
    expect(findMethodButton(wrapper, 'Milling')).toBeTruthy()
    expect(findMethodButton(wrapper, 'Grinding')).toBeFalsy()

    wrapper.unmount()
  })

  it('renders a kind icon and severity per step, independent of clickability', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: { items: [makeSummaryLot()], total: 1, limit: 25, skip: 0 },
        })
      }
      if (/^\/production-lots\/\d+$/.test(url)) {
        return Promise.resolve({ data: makeFullLot() })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    // Simple Mode: icon/severity is a Simple-Mode-only affordance (non-simple
    // mode's step-method-cell deliberately has neither, see the view).
    const { wrapper } = mountView({ simpleMode: true })
    await flushPromises()
    await flushPromises()

    const tags = wrapper.findAllComponents({ name: 'Tag' })
    const unassignedTag = tags.find((t) => t.text() === 'Milling')!
    const externalTag = tags.find((t) => t.text() === 'Turning')!

    expect(unassignedTag.props('icon')).toBeUndefined()
    expect(unassignedTag.props('severity')).toBe('secondary')
    expect(externalTag.props('icon')).toBe('mdi mdi-cart')
    expect(externalTag.props('severity')).toBe('info')

    wrapper.unmount()
  })

  it('shows success only for a completed position, not just a capability match', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: {
            items: [
              makeSummaryLot({
                steps: [
                  {
                    public_id: '11111111-1111-1111-1111-111111111111',
                    id: 1,
                    created: '2026-07-01',
                    note: null,
                    estimated_setup_minutes: null,
                    estimated_minutes_per_piece: null,
                    time_budget_per_piece: null,
                    sequence: 1,
                    creator_id: 1,
                    fabrication_method_id: 1,
                    role: 'fabrication' as const,
                    inspection_method_id: null,
                    inspection_method_name: null,
                    inspection_method_requires_evidence: null,
                    fabrication_method_name: { enGB: 'Milling' },
                    fabrication_method_requires_machine: true,
                    fabrication_method_required_external: false,
                    fabrication_method_default_supplier_id: null,
                    lot_id: 1,
                    position_id: 1,
                    source_process_id: null,
                    position_kind: 'external',
                    position_needs_machine: false,
                    position_status: 'completed',
                    position_quantity: 10,
                    position_quantity_remaining: 0,
                    actions: [],
                  },
                ],
              }),
            ],
            total: 1,
            limit: 25,
            skip: 0,
          },
        })
      }
      if (/^\/production-lots\/\d+$/.test(url)) {
        return Promise.resolve({ data: makeFullLot() })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    // Simple Mode: same reasoning as the icon/severity test above.
    const { wrapper } = mountView({ simpleMode: true })
    await flushPromises()
    await flushPromises()

    const tags = wrapper.findAllComponents({ name: 'Tag' })
    const completedTag = tags.find((t) => t.text() === 'Milling')!

    expect(completedTag.props('severity')).toBe('success')

    wrapper.unmount()
  })

  it('groups the header in Simple Mode too, over the source pair', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: { items: [makeSummaryLot()], total: 1, limit: 25, skip: 0 },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const { wrapper } = mountView({ simpleMode: true })
    await flushPromises()
    await flushPromises()

    const headerRows = wrapper.findAll('thead > tr')
    expect(headerRows).toHaveLength(3)

    const groups = headerRows[0]!.findAll('th')
    // Simple Mode's source is a single cell, so its group covers just that
    // and the material's delivery date.
    expect(groups.find((th) => th.text() === 'Source')?.attributes('colspan')).toBe('2')
    // Its steps are tags in one cell: nothing to group them over, so the
    // column reaches down through both header rows instead.
    expect(groups.find((th) => th.text() === 'Steps')?.attributes('rowspan')).toBe('2')

    expect(headerRows[1]!.findAll('th').map((th) => th.text())).toEqual(['Item', 'Delivery'])

    wrapper.unmount()
  })

  it('collapses a multi-step position into one column-group in Widescreen Mode', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: { items: [makeGroupedLot()], total: 1, limit: 25, skip: 0 },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    // Both steps share one position: a single Step column-group, not two.
    const headerRows = wrapper.findAll('thead > tr')
    const stepGroups = headerRows[0]!.findAll('th').filter((th) => th.text().startsWith('Step'))
    expect(stepGroups).toHaveLength(1)

    expect(wrapper.text()).toContain('Milling and Turning')

    wrapper.unmount()
  })

  it('collapses a multi-step position into one chip in Simple Mode, selectable as a whole', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: { items: [makeGroupedLot()], total: 1, limit: 25, skip: 0 },
        })
      }
      if (/^\/production-lots\/\d+$/.test(url)) {
        return Promise.resolve({ data: makeFullLot() })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const { wrapper, selectionStore } = mountView({ simpleMode: true })
    await flushPromises()
    await flushPromises()
    await openManageOrders(wrapper)

    const tags = wrapper.findAllComponents({ name: 'Tag' })
    const chips = tags.filter((tag) => tag.text().includes('Milling'))
    expect(chips).toHaveLength(1)
    expect(chips[0]!.text()).toContain('and Turning')

    await chips[0]!.trigger('click')
    await flushPromises()

    // Clicking the combined chip selects the whole position, same as a
    // single-step chip would.
    expect(selectionStore.items).toHaveLength(1)
    expect(selectionStore.items[0]).toMatchObject({ lotId: 1, position: { id: 1 } })

    wrapper.unmount()
  })
})

// Coverage-filter wiring mirrors notFullyAllocatedOnly's own
// arm-on-open / Clear-disarms-without-closing semantics (see
// boughtItemsDemandsFiltersStore.ts), applied to Manage Production's own
// machine/pool target selection instead of a boolean toggle.
describe('ProductionLotsListView coverage filter', () => {
  beforeEach(async () => {
    getMock.mockReset()
    getMock.mockImplementation(() =>
      Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } }),
    )
    await router.push('/')
    useLotDetail().visible.value = false
    useLotDetail().lotId.value = null
  })

  function lastLotsParams(): Record<string, unknown> | undefined {
    const calls = getMock.mock.calls.filter(([url]) => url === '/production-lots/')
    return calls.at(-1)?.[1]?.params
  }

  it('is unarmed and inactive before the panel is opened', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    const filtersStore = useProductionLotsFiltersStore()
    expect(filtersStore.coverageFilterArmed).toBe(false)
    expect(filtersStore.hasActiveFilters).toBe(false)
    expect(lastLotsParams()).not.toHaveProperty('coverable_by_any_pool')

    wrapper.unmount()
  })

  it('arms on panel open, counts as an active filter, and derives coverable_by_any_pool with no target picked', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageProduction(wrapper)

    const filtersStore = useProductionLotsFiltersStore()
    expect(filtersStore.coverageFilterArmed).toBe(true)
    expect(filtersStore.hasActiveFilters).toBe(true)
    expect(lastLotsParams()).toMatchObject({ coverable_by_any_pool: true })

    wrapper.unmount()
  })

  it('re-derives to coverable_by_machine_id when the target selection changes to a machine', async () => {
    const { wrapper, selectionStore } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageProduction(wrapper)

    selectionStore.selectedMachine = {
      id: 4,
      public_id: '44444444-4444-4444-4444-444444444444',
      archived: false,
      created: '2026-07-01',
      changed: null,
      changed_by_id: null,
      changed_by_full_name: '',
      internal_name: 'Mill A',
      vendor: 'Acme',
      model: 'M1',
      fabrication_method_ids: [1],
      fabrication_methods: [],
      max_part_dimension: null,
      note: null,
      is_qa_machine: false,
      creator_id: 1,
      creator_full_name: 'Tester',
      changes: [],
      open_downtime: null,
      status: 'idle',
      active_orders: [],
      live_order_count: 0,
    }
    await flushPromises()

    const params = lastLotsParams()
    expect(params).toMatchObject({ coverable_by_machine_id: 4 })
    expect(params).not.toHaveProperty('coverable_by_any_pool')

    wrapper.unmount()
  })

  it('Clear disarms the filter and drops the param without closing the panel', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageProduction(wrapper)

    const filtersStore = useProductionLotsFiltersStore()
    expect(filtersStore.coverageFilterArmed).toBe(true)

    const clearButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Clear')
    expect(clearButton).toBeTruthy()
    await clearButton!.trigger('click')
    await flushPromises()

    expect(filtersStore.coverageFilterArmed).toBe(false)
    expect(lastLotsParams()).not.toHaveProperty('coverable_by_any_pool')
    // The panel itself is still open; Clear only widens the list.
    expect(wrapper.find('.manage-production-panel').exists()).toBe(true)

    wrapper.unmount()
  })

  it('re-arms on panel reopen after Clear', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageProduction(wrapper)

    const filtersStore = useProductionLotsFiltersStore()
    filtersStore.clearAll()
    await flushPromises()
    expect(filtersStore.coverageFilterArmed).toBe(false)

    // Toggling the button twice closes, then reopens, the panel.
    await openManageProduction(wrapper)
    await openManageProduction(wrapper)

    expect(filtersStore.coverageFilterArmed).toBe(true)

    wrapper.unmount()
  })

  it('the smartFilterEnabled toggle drops both actionable_for and coverable_by_* while the panel stays armed', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageProduction(wrapper)

    const filtersStore = useProductionLotsFiltersStore()
    expect(filtersStore.coverageFilterArmed).toBe(true)
    expect(lastLotsParams()).toMatchObject({ actionable_for: 'machines' })
    expect(lastLotsParams()).toHaveProperty('coverable_by_any_pool')

    filtersStore.toggleSmartFilter()
    await flushPromises()

    const params = lastLotsParams()
    expect(params).not.toHaveProperty('actionable_for')
    expect(params).not.toHaveProperty('coverable_by_any_pool')
    expect(params).not.toHaveProperty('coverable_by_machine_id')
    expect(params).not.toHaveProperty('coverable_by_pool_id')
    // Arming state itself is untouched; toggling back on immediately
    // restores filtering without needing to close/reopen the panel.
    expect(filtersStore.coverageFilterArmed).toBe(true)

    filtersStore.toggleSmartFilter()
    await flushPromises()

    expect(lastLotsParams()).toMatchObject({ actionable_for: 'machines' })
    expect(lastLotsParams()).toHaveProperty('coverable_by_any_pool')

    wrapper.unmount()
  })
})

// Manage Orders/Manage Source parity with Manage Production's own
// behaviour: each sends its own actionable_for unconditionally while open
// (gated by smartFilterEnabled), and each must count toward
// hasActiveFilters/enable Clear the same way Production's coverageFilterArmed
// does, so Clear never stays disabled while these two panels are genuinely
// filtering.
describe('ProductionLotsListView actionable filter parity (Orders/Source)', () => {
  beforeEach(async () => {
    getMock.mockReset()
    getMock.mockImplementation(() =>
      Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } }),
    )
    await router.push('/')
    useLotDetail().visible.value = false
    useLotDetail().lotId.value = null
  })

  function lastLotsParams(): Record<string, unknown> | undefined {
    const calls = getMock.mock.calls.filter(([url]) => url === '/production-lots/')
    return calls.at(-1)?.[1]?.params
  }

  it('Manage Orders arms actionableFilterArmed, enables Clear, and sends actionable_for=orders', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    const filtersStore = useProductionLotsFiltersStore()
    expect(filtersStore.actionableFilterArmed).toBe(false)
    expect(filtersStore.hasActiveFilters).toBe(false)

    await openManageOrders(wrapper)

    expect(filtersStore.actionableFilterArmed).toBe(true)
    expect(filtersStore.hasActiveFilters).toBe(true)
    expect(lastLotsParams()).toMatchObject({ actionable_for: 'orders' })

    wrapper.unmount()
  })

  it('Manage Source arms actionableFilterArmed, enables Clear, and sends actionable_for=source', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageSource(wrapper)

    const filtersStore = useProductionLotsFiltersStore()
    expect(filtersStore.actionableFilterArmed).toBe(true)
    expect(filtersStore.hasActiveFilters).toBe(true)
    expect(lastLotsParams()).toMatchObject({ actionable_for: 'source' })

    wrapper.unmount()
  })

  it('smartFilterEnabled gates actionable_for for Manage Orders too', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageOrders(wrapper)

    const filtersStore = useProductionLotsFiltersStore()
    expect(lastLotsParams()).toMatchObject({ actionable_for: 'orders' })

    filtersStore.toggleSmartFilter()
    await flushPromises()

    expect(lastLotsParams()).not.toHaveProperty('actionable_for')
    // Arming state itself is untouched, same as Production's own case.
    expect(filtersStore.actionableFilterArmed).toBe(true)

    wrapper.unmount()
  })

  it('Clear disarms actionableFilterArmed and drops actionable_for without closing Manage Orders', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()
    await openManageOrders(wrapper)

    const filtersStore = useProductionLotsFiltersStore()
    expect(filtersStore.hasActiveFilters).toBe(true)

    const clearButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Clear')
    expect(clearButton).toBeTruthy()
    await clearButton!.trigger('click')
    await flushPromises()

    expect(filtersStore.actionableFilterArmed).toBe(false)
    expect(filtersStore.smartFilterEnabled).toBe(false)
    expect(lastLotsParams()).not.toHaveProperty('actionable_for')
    // The panel itself is still open; Clear only widens the list, same
    // contract as Manage Production's own Clear behaviour.
    expect(wrapper.find('.manage-orders-panel').exists()).toBe(true)

    wrapper.unmount()
  })
})

describe('ProductionLotsListView needs-assignment filter', () => {
  beforeEach(async () => {
    getMock.mockReset()
    getMock.mockImplementation(() =>
      Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } }),
    )
    await router.push('/')
    useLotDetail().visible.value = false
    useLotDetail().lotId.value = null
  })

  function lastLotsParams(): Record<string, unknown> | undefined {
    const calls = getMock.mock.calls.filter(([url]) => url === '/production-lots/')
    return calls.at(-1)?.[1]?.params
  }

  it('is off by default and sends no statuses param', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    expect(useProductionLotsFiltersStore().needsAssignmentOnly).toBe(false)
    expect(lastLotsParams()).not.toHaveProperty('statuses')

    wrapper.unmount()
  })

  it('sends statuses=[draft, partially_planned] when toggled on, overriding a single statusFilter', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    const filtersStore = useProductionLotsFiltersStore()
    filtersStore.statusFilter = 'completed'
    await flushPromises()
    expect(lastLotsParams()).toMatchObject({ status: 'completed' })

    filtersStore.toggleNeedsAssignmentOnly()
    await flushPromises()

    const params = lastLotsParams()
    expect(params).toMatchObject({ statuses: ['draft', 'partially_planned'] })
    expect(params).not.toHaveProperty('status')

    wrapper.unmount()
  })
})

// The lots list gives top-bar feedback while filtering/sorting, like its
// structurally identical siblings (OrdersTable.vue, ProductionQaView.vue).
// watchLoadingBar wires the lots
// store's own `loading` into the shared header bar. This only proves the
// wiring reacts, not the bar's own start/stop mechanics (those are
// router/__tests__/loadingBar.spec.ts's job).
describe('ProductionLotsListView loading bar', () => {
  beforeEach(async () => {
    getMock.mockReset()
    await router.push('/')
    useLotDetail().visible.value = false
    useLotDetail().lotId.value = null
  })

  it('feeds the lots store loading state into the header loading bar', async () => {
    let resolveLots: (value: unknown) => void = () => {}
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return new Promise((resolve) => {
          resolveLots = resolve
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const { wrapper } = mountView()
    await flushPromises()

    const loadingBarStore = useLoadingBarStore()
    const stopSpy = vi.spyOn(loadingBarStore, 'stop')

    // The lots fetch is still in flight; the bar must already be showing.
    expect(loadingBarStore.isLoading).toBe(true)

    resolveLots({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    await flushPromises()

    // The store's `loading` flipped back to false once the fetch settled:
    // the watcher must have released its hold on the bar in response.
    expect(stopSpy).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })
})

// selectionMode="single" makes LotsTable's rows keyboard-
// reachable and gives Enter the same effect as a click, via the shared
// useRowOpenGuard recipe proven on OrdersTable/ArticleGroupManagementTable.
// LotsTable is the one table with its own bulk
// selection (the edit-mode/Manage-Source checkbox column, driven by
// `:selection`/`:selectionMode` computeds already keyed off editStore/
// showManageSource); "single" mode is only ever bound while neither is
// active (`canOpenRow`), so the two must never fight over the same prop;
// that's what the last test here proves. Exercised through the full view
// (LotsTable has no dedicated spec) so the real lots-store
// wiring and manage-panel plumbing are in play, not a hand-stubbed mount.
describe('ProductionLotsListView row keyboard access', () => {
  beforeEach(async () => {
    getMock.mockReset()
    await router.push('/')
    useLotDetail().visible.value = false
    useLotDetail().lotId.value = null
  })

  function mockLotsList(): void {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: { items: [makeSummaryLot()], total: 1, limit: 25, skip: 0 },
        })
      }
      if (/^\/production-lots\/\d+$/.test(url)) {
        return Promise.resolve({ data: makeFullLot() })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })
  }

  it('makes the first row keyboard-focusable outside every manage mode', async () => {
    mockLotsList()
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')

    wrapper.unmount()
  })

  it('opens the lot detail on @row-select the same way @row-click does', async () => {
    mockLotsList()
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    expect(useLotDetail().visible.value).toBe(false)

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', {
      data: makeSummaryLot(),
      index: 0,
      originalEvent: new Event('keydown'),
    })
    await flushPromises()

    expect(useLotDetail().visible.value).toBe(true)
    expect(useLotDetail().lotId.value).toBe(1)

    wrapper.unmount()
  })

  // LotsTable has the highest-risk selection wiring. Bound to a
  // `rowSelection` ref outside every manage mode, the click below would put
  // a row into that ref, OpenVue's own tabindex computation (BodyRow.vue
  // #rowTabindex) would return -1 for every row, permanently, and the table
  // would be keyboard-unreachable from the very first open. `selection` is
  // bound to `undefined` outside every manage mode (see the comment above
  // `canOpenRow`'s selection wiring in LotsTable.vue), so it stays null and
  // the table stays reachable.
  it('stays keyboard-reachable (first row tabindex 0) after opening a row via click, outside every manage mode', async () => {
    mockLotsList()
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.attributes('tabindex')).toBe('0')

    await row.trigger('click')
    await flushPromises()

    expect(useLotDetail().visible.value).toBe(true)
    expect(wrapper.find('tr[data-p-selectable-row="true"]').attributes('tabindex')).toBe('0')

    wrapper.unmount()
  })

  it('stays keyboard-reachable (first row tabindex 0) after opening a row via Enter, outside every manage mode', async () => {
    mockLotsList()
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.attributes('tabindex')).toBe('0')

    await row.trigger('keydown', { code: 'Enter' })
    await flushPromises()

    expect(useLotDetail().visible.value).toBe(true)
    expect(wrapper.find('tr[data-p-selectable-row="true"]').attributes('tabindex')).toBe('0')

    wrapper.unmount()
  })

  // The bulk-edit checkbox column (editStore.editMode) binds this same
  // DataTable's `selection`/`selectionMode` to an array
  // (editStore.selectedItems) for batch actions; the row-open wiring must
  // not fight it ("do not clobber existing nested selection" guard,
  // verified empirically).
  it('does not clobber the bulk-edit selection array when a row is checked, then clicked, in edit mode', async () => {
    mockLotsList()
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    const editStore = useProductionLotsEditStore()
    editStore.editMode = true
    await flushPromises()

    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(editStore.selectedItems).toHaveLength(1)
    expect(editStore.selectedItems[0]).toMatchObject({ id: 1 })

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(editStore.selectedItems).toHaveLength(1)
    expect(editStore.selectedItems[0]).toMatchObject({ id: 1 })

    wrapper.unmount()
  })
})
