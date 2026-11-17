import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

import { useProductionLotsEditStore } from '../../stores/productionLotsEditStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { makeUserResponse } from '@/test-utils/factories'

import type {
  FabricationLotStep,
  LotSummaryResponse,
  LotSummaryStepExtra,
  LotSummaryStepResponse,
} from '../../../types/productionLotsResponse'

function makeStep(
  overrides: Partial<FabricationLotStep & LotSummaryStepExtra> = {},
): LotSummaryStepResponse {
  return {
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
    role: 'fabrication',
    inspection_method_id: null,
    inspection_method_name: null,
    inspection_method_requires_evidence: null,
    fabrication_method_name: { enGB: 'Milling' },
    fabrication_method_requires_machine: false,
    fabrication_method_required_external: false,
    fabrication_method_default_supplier_id: null,
    lot_id: 1,
    position_id: 1,
    source_process_id: null,
    position_kind: 'unassigned',
    position_needs_machine: false,
    position_status: 'pending',
    position_quantity: 10,
    position_quantity_remaining: 10,
    actions: [],
    ...overrides,
  }
}

function makeSummaryLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
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
    steps: [makeStep()],
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
    ...overrides,
  }
}

// Positions ride along on the list response (LotSummaryPositionResponse)
// rather than being fetched per lot, so the fixture derives one per distinct
// step position.
function withPositions(lot: LotSummaryResponse): LotSummaryResponse {
  return {
    ...lot,
    positions: [...new Set((lot.steps ?? []).map((s) => s.position_id))].map((positionId) => ({
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
  }
}

const getMock = vi.fn<(url: string) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    patch: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import ProductionLotsListView from '../ProductionLotsListView.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/', component: { template: '<div />' } }],
})

function mountView(options: { editMode?: boolean; striped?: boolean } = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse({ is_systemuser: true })
  if (options.editMode) useProductionLotsEditStore().editMode = true
  if (options.striped) useLayoutStore().applyVisualAids(false, false, true)
  const wrapper = mountWithApp(ProductionLotsListView, {
    pinia,
    attachTo: document.body,
    global: {
      plugins: [router, ConfirmationService],
      stubs: { RouterLink: true },
    },
  })
  return { wrapper }
}

function bodyRows(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('tbody > tr')
}

describe('ProductionLotsListView column mode', () => {
  beforeEach(async () => {
    getMock.mockReset()
    await router.push('/')
  })

  function mockLots(lots: LotSummaryResponse[]) {
    const items = lots.map(withPositions)
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: { items, total: items.length, limit: 25, skip: 0 },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })
  }

  it('renders one row per step and rowspans the lot-level cells', async () => {
    mockLots([
      makeSummaryLot({
        steps: [
          makeStep({ id: 1, sequence: 1, position_id: 1, fabrication_method_name: { enGB: 'Milling' } }),
          makeStep({ id: 2, sequence: 2, position_id: 2, fabrication_method_name: { enGB: 'Turning' } }),
          makeStep({ id: 3, sequence: 3, position_id: 3, fabrication_method_name: { enGB: 'Grinding' } }),
        ],
      }),
    ])

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    // One physical row per step of the single lot.
    expect(bodyRows(wrapper)).toHaveLength(3)

    // Every step's method is rendered, each in its own row.
    const text = wrapper.text()
    expect(text).toContain('Milling')
    expect(text).toContain('Turning')
    expect(text).toContain('Grinding')

    // The lot-level cells appear once, rowspanned across the 3 step rows,
    // rather than repeated per row.
    const lotNumberCells = wrapper.findAll('td').filter((td) => td.text() === 'LOT-1')
    expect(lotNumberCells).toHaveLength(1)
    expect(lotNumberCells[0]!.attributes('rowspan')).toBe('3')

    wrapper.unmount()
  })

  it('keeps a lot with no steps as a single row instead of dropping it', async () => {
    mockLots([makeSummaryLot({ steps: [] })])

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    expect(bodyRows(wrapper)).toHaveLength(1)
    expect(wrapper.text()).toContain('LOT-1')

    wrapper.unmount()
  })

  it('collapses a multi-step position into one combined row', async () => {
    mockLots([
      makeSummaryLot({
        steps: [
          makeStep({
            id: 1,
            sequence: 1,
            position_id: 1,
            fabrication_method_name: { enGB: 'Milling' },
            estimated_setup_minutes: 5,
          }),
          makeStep({
            id: 2,
            sequence: 2,
            position_id: 1,
            fabrication_method_name: { enGB: 'Turning' },
            estimated_setup_minutes: 3,
          }),
        ],
      }),
    ])

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    // Both steps share position_id 1: one combined row, not two.
    expect(bodyRows(wrapper)).toHaveLength(1)

    const text = wrapper.text()
    expect(text).toContain('Milling and Turning')
    // Setup times summed: 5 + 3 = 8 min.
    expect(text).toContain('8 min')

    const badge = wrapper.find('.step-count-badge')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toBe('2')

    wrapper.unmount()
  })

  it('groups each lot separately when several lots are visible', async () => {
    mockLots([
      makeSummaryLot({
        id: 1,
        lot_number: 'LOT-1',
        steps: [
          makeStep({ id: 1, sequence: 1, position_id: 1 }),
          makeStep({ id: 2, sequence: 2, position_id: 2 }),
        ],
      }),
      makeSummaryLot({
        id: 2,
        lot_number: 'LOT-2',
        steps: [makeStep({ id: 3, lot_id: 2, sequence: 1 })],
      }),
    ])

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    // 2 step rows for LOT-1 + 1 for LOT-2.
    expect(bodyRows(wrapper)).toHaveLength(3)

    const lot1 = wrapper.findAll('td').filter((td) => td.text() === 'LOT-1')
    const lot2 = wrapper.findAll('td').filter((td) => td.text() === 'LOT-2')
    expect(lot1).toHaveLength(1)
    expect(lot1[0]!.attributes('rowspan')).toBe('2')
    expect(lot2).toHaveLength(1)
    // A single-row group gets no rowspan attribute at all (OpenVue returns
    // null for a group of size 1).
    expect(lot2[0]!.attributes('rowspan')).toBeUndefined()

    wrapper.unmount()
  })

  it('renders Note as the last step column', async () => {
    mockLots([makeSummaryLot()])

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    const headers = wrapper.findAll('thead th').map((th) => th.text())
    const noteIndex = headers.indexOf('Note')
    const deliveryIndex = headers.indexOf('Delivery Date')
    expect(noteIndex).toBeGreaterThan(-1)
    expect(deliveryIndex).toBeGreaterThan(-1)
    // Note moved to the end of the step group, after Delivery Date.
    expect(noteIndex).toBeGreaterThan(deliveryIndex)
    // ...and it is the final step column (only the trailing lot-level
    // columns come after it).
    expect(headers.slice(noteIndex + 1)).not.toContain('Method')

    wrapper.unmount()
  })

  it('keeps the grouped header, with a single Step group over the step columns', async () => {
    mockLots([
      makeSummaryLot({
        steps: [makeStep({ id: 1, sequence: 1 }), makeStep({ id: 2, sequence: 2 })],
      }),
    ])

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    // Group row, sub-header row, filter row.
    const headerRows = wrapper.findAll('thead > tr')
    expect(headerRows).toHaveLength(3)

    const groups = headerRows[0]!.findAll('th')
    expect(groups.find((th) => th.text() === 'Source')?.attributes('colspan')).toBe('3')
    // Both steps share one set of step columns here, so one group covers
    // all 8 of them. Widescreen Mode is what repeats the group per step.
    const stepGroups = groups.filter((th) => th.text().startsWith('Step'))
    expect(stepGroups).toHaveLength(1)
    expect(stepGroups[0]!.attributes('colspan')).toBe('8')

    const subHeaders = headerRows[1]!.findAll('th').map((th) => th.text())
    expect(subHeaders.slice(0, 3)).toEqual(['Item', 'Status', 'Delivery'])
    expect(subHeaders).toContain('Method')

    wrapper.unmount()
  })

  it('rowspans the bulk-edit selection checkbox to one per lot', async () => {
    mockLots([
      makeSummaryLot({
        steps: [makeStep({ id: 1, sequence: 1 }), makeStep({ id: 2, sequence: 2 })],
      }),
    ])

    const { wrapper } = mountView({ editMode: true })
    await flushPromises()
    await flushPromises()

    // One checkbox for the lot, not one per step row.
    const checkboxes = wrapper.get('tbody').findAllComponents({ name: 'Checkbox' })
    expect(checkboxes).toHaveLength(1)

    wrapper.unmount()
  })

  it('is the default mode, with no store flag set', async () => {
    mockLots([
      makeSummaryLot({
        steps: [
          makeStep({ id: 1, sequence: 1, position_id: 1 }),
          makeStep({ id: 2, sequence: 2, position_id: 2 }),
        ],
      }),
    ])

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    // One row per position; Widescreen Mode would render the lot as one row.
    expect(bodyRows(wrapper)).toHaveLength(2)

    wrapper.unmount()
  })

  it('stripes per lot rather than per step row', async () => {
    mockLots([
      makeSummaryLot({
        id: 1,
        lot_number: 'LOT-1',
        steps: [
          makeStep({ id: 1, sequence: 1, position_id: 1 }),
          makeStep({ id: 2, sequence: 2, position_id: 2 }),
        ],
      }),
      makeSummaryLot({
        id: 2,
        lot_number: 'LOT-2',
        steps: [
          makeStep({ id: 3, lot_id: 2, sequence: 1, position_id: 3 }),
          makeStep({ id: 4, lot_id: 2, sequence: 2, position_id: 4 }),
        ],
      }),
    ])

    const { wrapper } = mountView({ striped: true })
    await flushPromises()
    await flushPromises()

    const rows = bodyRows(wrapper)
    expect(rows).toHaveLength(4)
    // Both of LOT-1's rows unstriped, both of LOT-2's striped: OpenVue's
    // own per-row striping would have alternated within each lot instead.
    const striped = rows.map((row) => row.classes('lot-row--striped'))
    expect(striped).toEqual([false, false, true, true])
    // ...and OpenVue's striping is off, so the two can't stack.
    expect(wrapper.findComponent({ name: 'DataTable' }).classes()).not.toContain(
      'p-datatable-striped',
    )

    wrapper.unmount()
  })

  it('marks every row of a lot on hover, whichever of its rows is hovered', async () => {
    mockLots([
      makeSummaryLot({
        id: 1,
        lot_number: 'LOT-1',
        steps: [
          makeStep({ id: 1, sequence: 1, position_id: 1 }),
          makeStep({ id: 2, sequence: 2, position_id: 2 }),
          makeStep({ id: 3, sequence: 3, position_id: 3 }),
        ],
      }),
      makeSummaryLot({
        id: 2,
        lot_number: 'LOT-2',
        steps: [makeStep({ id: 4, lot_id: 2, sequence: 1 })],
      }),
    ])

    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    // Hover the lot's *last* step row: the lot-level cells live in its
    // first row, so nothing but a lot-wide highlight covers both.
    await bodyRows(wrapper)[2]!.find('td').trigger('mouseover')
    await flushPromises()

    expect(bodyRows(wrapper).map((row) => row.classes('lot-row--hovered'))).toEqual([
      true,
      true,
      true,
      false,
    ])

    wrapper.unmount()
  })
})
