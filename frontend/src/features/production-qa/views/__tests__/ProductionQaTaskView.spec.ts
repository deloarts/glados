import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useHostStore } from '@/core/host/stores/hostStore'
import {
  RouteStub,
  makeLotResponse,
  makeProductionOrderResponse,
  makeTestRouter,
} from '@/test-utils/factories'
import type {
  ProductionOrderCompletionResponse,
  ProductionOrderResponse,
} from '@/features/production'
import type { LotResponse, LotStepResponse } from '@/features/production'

// Generic fallback for anything not mocked below. File lists are plain
// arrays, every other GET is a paginated envelope.
const apiPostMock = vi.fn<(url: string, body?: unknown) => Promise<{ data: unknown }>>()
let inspectionMethods: unknown[] = []
vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) =>
      Promise.resolve({
        data: url.endsWith('/files')
          ? []
          : url === '/inspection-methods/'
            ? { items: inspectionMethods, total: inspectionMethods.length }
            : { items: [], total: 0 },
      }),
    post: (url: string, body?: unknown) => apiPostMock(url, body),
  },
}))

const getProductionOrderMock = vi.fn<() => Promise<ProductionOrderResponse>>()
const getLotMock = vi.fn<() => Promise<LotResponse>>()
// Only getProductionOrder/getLot are mocked. Everything else re-exported by
// the barrel (ProductionOrderCompletionDialog, useProductionOrderFilesStore,
// getProductionOrderFileBlob, productionOrderStatusSeverity) stays real.
vi.mock('@/features/production', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/production')>()),
  getProductionOrder: () => getProductionOrderMock(),
  getLot: () => getLotMock(),
}))

let hasPermissionMock: (permission?: string) => boolean = () => true
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({
    hasPermission: (permission: string) => hasPermissionMock(permission),
  }),
}))

import ProductionQaTaskView from '../ProductionQaTaskView.vue'

vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

const INSPECTION_STEP_BASE = {
  id: 2,
  public_id: '22222222-2222-2222-2222-222222222222',
  created: '2026-07-01',
  note: null,
  estimated_setup_minutes: null,
  estimated_minutes_per_piece: null,
  time_budget_per_piece: null,
  sequence: 2,
  creator_id: 1,
  fabrication_method_id: null,
  role: 'inspection' as const,
  fabrication_method_name: { enGB: '' },
  fabrication_method_requires_machine: false,
  fabrication_method_required_external: false,
  fabrication_method_default_supplier_id: null,
  lot_id: 1,
  position_id: 1,
  source_process_id: null,
}

function makeInspectionStep(requiresEvidence: boolean): LotStepResponse {
  return {
    ...INSPECTION_STEP_BASE,
    inspection_method_id: 5,
    inspection_method_name: requiresEvidence ? { enGB: 'Measurement' } : { enGB: 'Visual Check' },
    inspection_method_requires_evidence: requiresEvidence,
  } as LotStepResponse
}

function makeFabricationStep(): LotStepResponse {
  return {
    ...INSPECTION_STEP_BASE,
    id: 3,
    role: 'fabrication',
    fabrication_method_id: 1,
    fabrication_method_name: { enGB: 'Milling' },
    inspection_method_id: null,
    inspection_method_name: null,
    inspection_method_requires_evidence: null,
  } as LotStepResponse
}

function makeOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  // A running order offers its completion, as the backend's actions say.
  return makeProductionOrderResponse({
    status: 'in_progress',
    quantity_completed: 4,
    actions: ['record_completion'],
    ...overrides,
  })
}

function makeUser(id: number, fullName: string) {
  return {
    id,
    public_id: `00000000-0000-0000-0000-${String(id).padStart(12, '0')}`,
    full_name: fullName,
    username: `user${id}`,
    email: `${id}@example.com`,
    has_avatar: false,
  }
}

function makeCompletion(
  overrides: Partial<ProductionOrderCompletionResponse> = {},
): ProductionOrderCompletionResponse {
  return {
    id: 1,
    public_id: '55555555-5555-5555-5555-555555555555',
    created: '2026-10-12',
    completion_date: '2026-10-12',
    note: null,
    operator_id: 7,
    operator: makeUser(7, 'Alex Inspector'),
    recorded_by_id: 7,
    recorded_by: makeUser(7, 'Alex Inspector'),
    production_order_id: 1,
    quantity: 2,
    quantity_accepted: 2,
    quantity_rejected: 0,
    quantity_rework: 0,
    quantity_scrap: 0,
    scrap_reason: null,
    ...overrides,
  } as ProductionOrderCompletionResponse
}

function makeLot(steps: LotStepResponse[]): LotResponse {
  return makeLotResponse({
    public_id: '11111111-1111-1111-1111-111111111111',
    lot_number: 'LOT-1',
    made_item_article_name: 'Widget',
    made_item_material: 'Steel',
    demand_status: 'open',
    project_id: 1,
    project_customer: 'Customer',
    positions: [
      {
        id: 1,
        public_id: '44444444-4444-4444-4444-444444444444',
        created: '2026-07-01',
        changed: null,
        changed_by: null,
        changed_by_id: null,
        sequence: 1,
        kind: 'internal',
        status: 'in_progress',
        quantity: 10,
        quantity_completed: 4,
        quantity_remaining: 6,
        note: null,
        creator_id: 1,
        lot_id: 1,
        steps,
        order_item_id: null,
        order_id: null,
        order_number: '',
        supplier_name: '',
        order_item_status: '',
        order_item_closed_short: false,
        earlier_order_lines: [],
        expected_delivery_date: null,
        production_orders: [],
        actions: [],
        planned_delivery_date: null,
        planned_pickup_date: null,
      },
    ],
    steps,
  })
}

function makeRouter() {
  return makeTestRouter([
    {
      path: '/production/qa/:orderId',
      name: 'ProductionQaTask',
      component: ProductionQaTaskView,
    },
    { path: '/production/qa', component: RouteStub },
  ])
}

async function mountView({ storageEnabled = false } = {}) {
  const router = makeRouter()
  await router.push('/production/qa/1')
  await router.isReady()

  const pinia: Pinia = createPinia()
  setActivePinia(pinia)
  useHostStore().storageEnabled = storageEnabled

  const wrapper = mountWithApp(ProductionQaTaskView, {
    pinia,
    attachTo: document.body,
    global: {
      plugins: [router],
      directives: { tooltip: Tooltip },
      stubs: {
        ProductionOrderCompletionDialog: true,
        ProductionOrderStartDialog: true,
        FilePreviewDialog: true,
        MeshViewer: true,
        MadeItemThumbnailCell: true,
      },
    },
  })
  await flushPromises()
  await flushPromises()
  return { wrapper, router }
}

function controlLabels(wrapper: Awaited<ReturnType<typeof mountView>>['wrapper']): string[] {
  return wrapper
    .find('[data-testid="controls-bar-start"]')
    .findAll('button')
    .map((b) => b.text())
}

function findButton(
  wrapper: Awaited<ReturnType<typeof mountView>>['wrapper'],
  label: string,
) {
  return wrapper.findAll('button').find((b) => b.text().includes(label))
}

describe('ProductionQaTaskView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProductionOrderMock.mockReset()
    getLotMock.mockReset()
    apiPostMock.mockReset()
    hasPermissionMock = () => true
    inspectionMethods = []
    document.body.innerHTML = ''
  })

  it('renders inside the standard PageLayout card and shows the task identity in the info bar', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder())
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))

    const { wrapper } = await mountView()

    const layout = wrapper.findComponent({ name: 'PageLayout' })
    expect(layout.exists()).toBe(true)
    expect(layout.props('card')).toBe(true)
    expect(wrapper.text()).toContain('PO-1')
    expect(wrapper.text()).toContain('Widget')
    expect(wrapper.text()).toContain('PN-1')
    expect(wrapper.text()).toContain('Visual Check')
  })

  it('routes back to the QA task list', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder())
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))

    const { wrapper, router } = await mountView()

    const back = wrapper.find('button[aria-label="Back to QA tasks"]')
    expect(back.exists()).toBe(true)
    await back.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/production/qa')
  })

  it('gates the record button on the write:inspections permission', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder())
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))

    hasPermissionMock = () => false
    const { wrapper: locked } = await mountView()
    const lockedRecord = locked.findAll('button').find((b) => b.text().includes('Record Result'))
    expect(lockedRecord?.attributes('disabled')).toBeDefined()

    hasPermissionMock = () => true
    const { wrapper: unlocked } = await mountView()
    const unlockedRecord = unlocked
      .findAll('button')
      .find((b) => b.text().includes('Record Result'))
    expect(unlockedRecord?.attributes('disabled')).toBeUndefined()
  })

  it('names the missing permission on the disabled Record Result and Add Document buttons', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder())
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))
    hasPermissionMock = () => false

    const { wrapper } = await mountView({ storageEnabled: true })

    for (const testId of ['qa-record', 'qa-add-document']) {
      const button = wrapper.get(`[data-testid="${testId}"]`)
      expect(button.attributes('disabled')).toBeDefined()
      const span = button.element.parentElement as HTMLElement & { $_ptooltipValue?: string }
      expect(span.$_ptooltipValue).toBe(
        'Recording inspection results needs the permission Record QA Inspections.',
      )
    }
  })

  it('names the missing permissions on a disabled Start QA', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder({ status: 'queued', actions: ['start'] }))
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))
    hasPermissionMock = () => false

    const { wrapper } = await mountView()

    const start = wrapper.get('[data-testid="qa-start"]')
    expect(start.attributes('disabled')).toBeDefined()
    const span = start.element.parentElement as HTMLElement & { $_ptooltipValue?: string }
    expect(span.$_ptooltipValue).toBe(
      'Starting a QA task needs the permissions Write Production Orders and Record QA Inspections.',
    )
  })

  it('lays a queued task out as back and start, then document and report, without record', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder({ status: 'queued', actions: ['start'] }))
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))

    const { wrapper } = await mountView({ storageEnabled: true })

    expect(controlLabels(wrapper)).toEqual([
      'Back to QA tasks',
      'Start QA',
      'Add Document',
      'Inspection Report',
    ])
  })

  it('offers record once the task runs', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder())
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))

    const { wrapper } = await mountView({ storageEnabled: true })

    expect(controlLabels(wrapper)).toContain('Record Result')
  })

  it('starts a queued task directly and refreshes the order', async () => {
    getProductionOrderMock
      .mockResolvedValueOnce(makeOrder({ status: 'queued' }))
      .mockResolvedValueOnce(makeOrder({ status: 'in_progress' }))
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))
    apiPostMock.mockResolvedValue({ data: makeOrder({ status: 'in_progress' }) })

    const { wrapper } = await mountView()

    await findButton(wrapper, 'Start QA')!.trigger('click')
    await flushPromises()

    expect(apiPostMock).toHaveBeenCalledWith('/production-orders/1/start', {})
    expect(getProductionOrderMock).toHaveBeenCalledTimes(2)
    expect(findButton(wrapper, 'Start QA')).toBeUndefined()
  })

  it('labels the start button as resume for a paused task', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder({ status: 'paused' }))
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))

    const { wrapper } = await mountView()

    expect(findButton(wrapper, 'Resume QA')).toBeDefined()
    expect(findButton(wrapper, 'Start QA')).toBeUndefined()
  })

  it('disables start without write:production_orders or when the backend says it cannot start', async () => {
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))

    hasPermissionMock = (permission) => permission !== 'write:production_orders'
    getProductionOrderMock.mockResolvedValue(makeOrder({ status: 'queued' }))
    const { wrapper: noPermission } = await mountView()
    expect(findButton(noPermission, 'Start QA')?.attributes('disabled')).toBeDefined()

    hasPermissionMock = () => true
    getProductionOrderMock.mockResolvedValue(makeOrder({ status: 'queued', can_start: false }))
    const { wrapper: notStartable } = await mountView()
    expect(findButton(notStartable, 'Start QA')?.attributes('disabled')).toBeDefined()
  })

  it('uploads picked documents as measurement reports of the order', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder())
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))
    apiPostMock.mockResolvedValue({
      data: {
        id: 9,
        production_order_id: 1,
        file_name: 'gauge.jpg',
        mime_type: 'image/jpeg',
        size_bytes: 3,
        category: 'measurement_report',
      },
    })

    const { wrapper } = await mountView({ storageEnabled: true })

    const input = wrapper.find<HTMLInputElement>('[data-testid="qa-document-input"]')
    const photo = new File(['abc'], 'gauge.jpg', { type: 'image/jpeg' })
    Object.defineProperty(input.element, 'files', { value: [photo], configurable: true })
    await input.trigger('change')
    await flushPromises()

    expect(apiPostMock).toHaveBeenCalledTimes(1)
    const [url, body] = apiPostMock.mock.calls[0]!
    expect(url).toBe('/production-orders/1/files')
    expect((body as FormData).get('category')).toBe('measurement_report')
    expect((body as FormData).get('file')).toBe(photo)
    expect(wrapper.text()).toContain('gauge.jpg')
  })

  it("opens the export dialog of the lot's inspection report", async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder())
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))

    const { wrapper } = await mountView()

    await findButton(wrapper, 'Inspection Report')!.trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('Export report')
  })

  it('says the task waits on its upstream step only while it is queued or paused', async () => {
    const waiting = "This task can't be started yet"
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))

    getProductionOrderMock.mockResolvedValue(makeOrder({ status: 'queued', can_start: false }))
    const { wrapper: queued } = await mountView()
    expect(queued.text()).toContain(waiting)

    getProductionOrderMock.mockResolvedValue(makeOrder({ status: 'in_progress', can_start: false }))
    const { wrapper: running } = await mountView()
    expect(running.text()).not.toContain(waiting)
  })

  it('shows the recorded results with totals, the inspector and the scrap reason', async () => {
    getProductionOrderMock.mockResolvedValue(
      makeOrder({
        status: 'completed',
        quantity_completed: 5,
        completions: [
          makeCompletion(),
          makeCompletion({
            id: 2,
            quantity: 3,
            quantity_accepted: 1,
            quantity_rejected: 2,
            quantity_scrap: 2,
            scrap_reason: 'out_of_tolerance',
            recorded_by_id: 8,
            recorded_by: makeUser(8, 'Sam Office'),
            note: 'Bore too wide',
          }),
        ],
      }),
    )
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))

    const { wrapper } = await mountView()

    const text = wrapper.text()
    expect(text).toContain('Results')
    expect(text).toContain('Alex Inspector')
    expect(text).toContain('recorded by Sam Office')
    expect(text).toContain('1 accepted, 2 rejected, 2 scrap (Out of Tolerance)')
    expect(text).toContain('Bore too wide')
  })

  it('says no results are recorded while the task has none', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder())
    getLotMock.mockResolvedValue(makeLot([makeInspectionStep(false)]))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('No results recorded yet.')
  })

  it('shows the method instructions, both notes and who started the task', async () => {
    inspectionMethods = [
      {
        id: 5,
        name: 'Visual Check',
        description: 'Check the surface for scratches.',
        label_color: '#123456',
        label_font_color: '#ffffff',
        requires_evidence: false,
        archived: false,
      },
    ]
    getProductionOrderMock.mockResolvedValue(
      makeOrder({ note: 'Customer is picky', started_operator: makeUser(9, 'Jo Starter') }),
    )
    getLotMock.mockResolvedValue(
      makeLot([{ ...makeInspectionStep(false), note: 'Check thread M8' }]),
    )

    const { wrapper } = await mountView()

    const text = wrapper.text()
    expect(text).toContain('Check the surface for scratches.')
    expect(text).toContain('Check thread M8')
    expect(text).toContain('Customer is picky')
    expect(text).toContain('Jo Starter')
  })

  it('shows the not-an-inspection message for a purely fabrication position', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder())
    getLotMock.mockResolvedValue(makeLot([makeFabricationStep()]))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('This production order is not an inspection task.')
  })
})
