import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import {
  RouteStub,
  makeProductionOrderResponse,
  makeTestRouter,
  userWithPermissions,
} from '@/test-utils/factories'

import type { ProductionOrderResponse } from '../../../types/productionOrdersResponse'
import type { ProductionMachineResponse } from '@/features/production-machines'
import type { MachinePoolResponse } from '@/features/production-machines'

// MachineDetailContent owns the whole record (the queue store, live
// refresh, a handful of order dialogs); none of that is this view's
// concern, so it's replaced with a stub that exposes exactly the contract
// MachineDetailView reads (MachineDetailView.vue's defineExpose block),
// driven by a shared `rawState` the tests mutate directly before mounting.
// Same idiom as production/lots/views/__tests__/LotDetailView.spec.ts.
const {
  rawState,
  onCardStartMock,
  onCardPauseMock,
  onCardCompleteMock,
  onCardCancelMock,
  onPrintMock,
  openItemDialogMock,
  openSourceItemDialogMock,
  openOrderDialogMock,
} = vi.hoisted(() => ({
  rawState: {
    machine: null as ProductionMachineResponse | null,
    ready: false,
    pools: [] as MachinePoolResponse[],
    machineState: 'idle' as 'running' | 'paused' | 'idle',
    machineStateTagSeverity: 'secondary' as string,
    canWrite: false,
    controlTarget: null as ProductionOrderResponse | null,
    controlCanOperateInspection: true,
    controlStartBlocked: true,
    controlStartBlockedTooltip: undefined as string | undefined,
    canPrint: false,
    printing: null as string | null,
    controlCanOpenItem: false,
    controlCanOpenSourceItem: false,
  },
  onCardStartMock: vi.fn<(order: ProductionOrderResponse) => void>(),
  onCardPauseMock: vi.fn<(order: ProductionOrderResponse) => void>(),
  onCardCompleteMock: vi.fn<(order: ProductionOrderResponse) => void>(),
  onCardCancelMock: vi.fn<(order: ProductionOrderResponse) => void>(),
  onPrintMock: vi.fn<(classifier: string) => void>(),
  openItemDialogMock: vi.fn<() => void>(),
  openSourceItemDialogMock: vi.fn<() => void>(),
  openOrderDialogMock: vi.fn<() => void>(),
}))

vi.mock('../../components/MachineDetailContent.vue', async () => {
  const { defineComponent, h, reactive, toRefs } = await import('vue')
  const state = reactive(rawState)

  const ContentStub = defineComponent({
    name: 'MachineDetailContent',
    props: { machineId: Number },
    setup(_, { expose }) {
      expose({
        ...toRefs(state),
        onCardStart: onCardStartMock,
        onCardPause: onCardPauseMock,
        onCardComplete: onCardCompleteMock,
        onCardCancel: onCardCancelMock,
        onPrint: onPrintMock,
        openItemDialog: openItemDialogMock,
        openSourceItemDialog: openSourceItemDialogMock,
        openOrderDialog: openOrderDialogMock,
      })
      return () => h('div', { class: 'machine-detail-content-stub' })
    },
  })

  return { default: ContentStub }
})

import MachineDetailView from '../MachineDetailView.vue'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'

function makeMachine(overrides: Partial<ProductionMachineResponse> = {}): ProductionMachineResponse {
  return {
    id: 7,
    public_id: '00000000-0000-0000-0000-000000000007',
    archived: false,
    created: '2026-07-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    internal_name: 'Mill 7',
    vendor: 'Contoso',
    model: 'VF-2',
    fabrication_method_ids: [2],
    fabrication_methods: [
      {
        id: 2,
        public_id: '20000000-0000-0000-0000-000000000002',
        created: '2026-01-01',
        changed: '2026-01-01T00:00:00Z',
        changed_by: null,
        changed_by_id: null,
        name: { enGB: 'Milling' },
        description: { enGB: '' },
        label_color: '#6366f1',
        label_font_color: '#ffffff',
        requires_machine: true,
        required_external: false,
        default_supplier_id: null,
        default_for_assemblies: false,
        archived: false,
        sort_order: 0,
        creator_id: 1,
        creator: null,
        lead_time_days: null,
        wait_after_minutes: null,
      },
    ],
    max_part_dimension: null,
    is_qa_machine: false,
    note: null,
    creator_id: 1,
    creator_full_name: 'Tester',
    changes: [],
    active_orders: [],
    live_order_count: 0,
    open_downtime: null,
    status: 'down',
    ...overrides,
  }
}

function makePool(overrides: Partial<MachinePoolResponse> = {}): MachinePoolResponse {
  return {
    id: 3,
    public_id: '10000000-0000-0000-0000-000000000003',
    archived: false,
    created: '2026-07-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    name: 'Pool A',
    machine_ids: [7],
    machines: [],
    note: null,
    creator_id: 1,
    creator_full_name: 'Tester',
    changes: [],
    ...overrides,
  }
}

// What the backend offers on a production order in each status, from the
// production order intent table (start and resume also need the lot, the
// machine and upstream input, which can_start reports).
const ORDER_ACTIONS: Record<string, LifecycleAction[]> = {
  queued: ['start', 'cancel', 'split', 'merge'],
  in_progress: ['pause', 'cancel', 'record_completion', 'scrap'],
  paused: ['resume', 'cancel'],
  completed: [],
  canceled: [],
}

function makeOrder(
  overrides: Partial<ProductionOrderResponse> & { id: number },
): ProductionOrderResponse {
  return makeProductionOrderResponse({
    actions: ORDER_ACTIONS[overrides.status ?? 'queued'],
    public_id: `33333333-3333-3333-3333-${String(overrides.id).padStart(12, '0')}`,
    production_order_number: `PO-${overrides.id}`,
    queue_sequence: overrides.id,
    machine_id: 7,
    machine_internal_name: 'Mill 7',
    ...overrides,
  })
}

/**
 * Mirrors the real route, constraint included, so the view reads its id the
 * same way it does in the app.
 */
function makeRouter() {
  return makeTestRouter([
    { path: '/production/machines/:id(\\d+)', name: 'MachineDetail', component: MachineDetailView },
    { path: '/production/queue', component: RouteStub },
  ])
}

// Every mounted view watches the same reactive `rawState`, so a view left
// mounted by an earlier test would still react to a later test mutating it,
// tear them down between tests.
const mounted: VueWrapper[] = []

// The signed-in user is user #1, the creator of every order makeOrder
// builds, unless a test passes other permissions or orders.
async function mountView(permissions: string[] = []) {
  const router = makeRouter()
  await router.push('/production/machines/42')
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const wrapper = mountWithApp(MachineDetailView, {
    pinia,
    global: {
      plugins: [router, ConfirmationService],
      directives: { tooltip: Tooltip },
    },
  })
  mounted.push(wrapper)
  await flushPromises()
  return { wrapper, router }
}

describe('MachineDetailView', () => {
  afterEach(() => {
    for (const wrapper of mounted) wrapper.unmount()
    mounted.length = 0
  })

  beforeEach(() => {
    Object.assign(rawState, {
      machine: null,
      ready: false,
      pools: [],
      machineState: 'idle',
      machineStateTagSeverity: 'secondary',
      canWrite: false,
      controlTarget: null,
      controlCanOperateInspection: true,
      controlStartBlocked: true,
      controlStartBlockedTooltip: undefined,
      canPrint: false,
      printing: null,
      controlCanOpenItem: false,
      controlCanOpenSourceItem: false,
    })
    onCardStartMock.mockReset()
    onCardPauseMock.mockReset()
    onCardCompleteMock.mockReset()
    onCardCancelMock.mockReset()
    onPrintMock.mockReset()
    openItemDialogMock.mockReset()
    openSourceItemDialogMock.mockReset()
    openOrderDialogMock.mockReset()
  })

  it('passes the numeric route id to MachineDetailContent', async () => {
    const { wrapper } = await mountView()

    const stub = wrapper.findComponent({ name: 'MachineDetailContent' })
    expect(stub.props('machineId')).toBe(42)
  })

  it('shows loading skeletons in the InfoBar while not ready and no machine yet', async () => {
    rawState.ready = false
    rawState.machine = null

    const { wrapper } = await mountView()

    expect(wrapper.find('.machine-name').exists()).toBe(false)
    expect(wrapper.findAllComponents({ name: 'Skeleton' }).length).toBe(2)
  })

  it('renders the machine identity, vendor/model, fabrication method, pool, and state tags once loaded', async () => {
    rawState.ready = true
    rawState.machine = makeMachine()
    rawState.pools = [makePool()]
    rawState.machineState = 'running'
    rawState.machineStateTagSeverity = 'warn'

    const { wrapper } = await mountView()
    const text = wrapper.text()

    expect(text).toContain('Mill 7')
    expect(text).toContain('Contoso VF-2')
    expect(text).toContain('Milling')
    expect(text).toContain('Pool A')
    expect(text).toContain('Running')
    expect(wrapper.findAllComponents({ name: 'Skeleton' }).length).toBe(0)
  })

  it('shows only the (all disabled) print/open buttons when there is no control target', async () => {
    rawState.controlTarget = null

    const { wrapper } = await mountView()

    const labels = wrapper
      .findAll('button')
      .map((b) => b.text())
      .filter((text) => text.length > 0)
    expect(labels).toEqual(['Print Docket', 'Open Item', 'Open Source Material', 'Open Order', 'Downtimes'])

    const splitButton = wrapper.findComponent({ name: 'SplitButton' })
    expect(splitButton.props('disabled')).toBe(true)

    for (const label of ['Open Item', 'Open Source Material', 'Open Order']) {
      const button = wrapper.findAll('button').find((b) => b.text() === label)
      expect(button!.attributes('disabled')).toBeDefined()
    }
  })

  it('the print split button posts the docket classifier on its main click, and the label classifier from its dropdown item', async () => {
    const order = makeOrder({ id: 20, status: 'in_progress' })
    rawState.controlTarget = order
    rawState.canPrint = true
    rawState.printing = null

    const { wrapper } = await mountView()

    const splitButton = wrapper.findComponent({ name: 'SplitButton' })
    expect(splitButton.props('disabled')).toBe(false)

    await splitButton.vm.$emit('click')
    expect(onPrintMock).toHaveBeenCalledWith('production_order_docket')

    const items = splitButton.props('model') as { label: string; command: () => void }[]
    const labelItem = items.find((i) => i.label === 'Print Label')
    expect(labelItem).toBeDefined()
    labelItem!.command()
    expect(onPrintMock).toHaveBeenCalledWith('production_order_label')
  })

  it('disables the print split button without the print:documents permission or while a print is in flight', async () => {
    rawState.controlTarget = makeOrder({ id: 21, status: 'in_progress' })
    rawState.canPrint = false

    const { wrapper } = await mountView()
    expect(wrapper.findComponent({ name: 'SplitButton' }).props('disabled')).toBe(true)

    rawState.canPrint = true
    rawState.printing = 'production_order_docket'
    await flushPromises()
    expect(wrapper.findComponent({ name: 'SplitButton' }).props('disabled')).toBe(true)
  })

  it('shows an enabled Start for a queued control target when canWrite and not blocked', async () => {
    rawState.controlTarget = makeOrder({ id: 1, status: 'queued' })
    rawState.canWrite = true
    rawState.controlStartBlocked = false

    const { wrapper } = await mountView()

    const startButton = wrapper.findAll('button').find((b) => b.text() === 'Start')
    expect(startButton).toBeTruthy()
    expect(startButton!.attributes('disabled')).toBeUndefined()
    expect(wrapper.findAll('button').some((b) => b.text() === 'Resume')).toBe(false)
  })

  it('disables Start when canWrite is false', async () => {
    rawState.controlTarget = makeOrder({ id: 2, status: 'queued' })
    rawState.canWrite = false
    rawState.controlStartBlocked = false

    const { wrapper } = await mountView()

    const startButton = wrapper.findAll('button').find((b) => b.text() === 'Start')
    expect(startButton).toBeTruthy()
    expect(startButton!.attributes('disabled')).toBeDefined()
  })

  it('disables Start when controlStartBlocked is true', async () => {
    rawState.controlTarget = makeOrder({ id: 3, status: 'queued' })
    rawState.canWrite = true
    rawState.controlStartBlocked = true

    const { wrapper } = await mountView()

    const startButton = wrapper.findAll('button').find((b) => b.text() === 'Start')
    expect(startButton).toBeTruthy()
    expect(startButton!.attributes('disabled')).toBeDefined()
  })

  it('shows Resume instead of Start when the control target is paused', async () => {
    rawState.controlTarget = makeOrder({ id: 4, status: 'paused' })
    rawState.canWrite = true
    rawState.controlStartBlocked = false

    const { wrapper } = await mountView()
    const labels = wrapper.findAll('button').map((b) => b.text())

    expect(labels).toContain('Resume')
    expect(labels).not.toContain('Start')
  })

  it('shows Pause and Complete only when the control target is in_progress', async () => {
    rawState.controlTarget = makeOrder({ id: 5, status: 'in_progress' })
    rawState.canWrite = true
    rawState.controlCanOperateInspection = true

    const { wrapper } = await mountView()
    const labels = wrapper.findAll('button').map((b) => b.text())

    expect(labels).toContain('Pause')
    expect(labels).toContain('Complete')
  })

  it('hides Pause and Complete for a queued or paused control target', async () => {
    rawState.controlTarget = makeOrder({ id: 6, status: 'queued' })
    rawState.canWrite = true

    const { wrapper } = await mountView()
    const labels = wrapper.findAll('button').map((b) => b.text())

    expect(labels).not.toContain('Pause')
    expect(labels).not.toContain('Complete')
  })

  it('shows Complete disabled with the reason (and Pause enabled) when controlCanOperateInspection is false', async () => {
    rawState.controlTarget = makeOrder({ id: 7, status: 'in_progress' })
    rawState.canWrite = true
    rawState.controlCanOperateInspection = false

    const { wrapper } = await mountView()

    const pause = wrapper.findAll('button').find((b) => b.text() === 'Pause')
    expect(pause!.attributes('disabled')).toBeUndefined()
    const complete = wrapper.get('[data-testid="machine-control-complete"]')
    expect(complete.attributes('disabled')).toBeDefined()
    const span = complete.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe(i18n.global.t('productionQueue.card.inspectionPermissionTooltip'))
  })

  it('names the missing permission on the disabled actions without canWrite', async () => {
    rawState.controlTarget = makeOrder({ id: 11, status: 'in_progress' })
    rawState.canWrite = false

    const { wrapper } = await mountView()

    const complete = wrapper.get('[data-testid="machine-control-complete"]')
    expect(complete.attributes('disabled')).toBeDefined()
    const span = complete.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Production Orders.')
  })

  it.each(['completed', 'canceled'] as const)(
    'hides Cancel when the control target is %s',
    async (status) => {
      rawState.controlTarget = makeOrder({ id: 8, status })
      rawState.canWrite = true

      const { wrapper } = await mountView()
      expect(wrapper.findAll('button').some((b) => b.text() === 'Cancel')).toBe(false)
    },
  )

  it.each(['queued', 'paused', 'in_progress'] as const)(
    'shows Cancel when the control target is %s',
    async (status) => {
      rawState.controlTarget = makeOrder({ id: 9, status })
      rawState.canWrite = true

      const { wrapper } = await mountView()
      expect(wrapper.findAll('button').some((b) => b.text() === 'Cancel')).toBe(true)
    },
  )

  it("shows Cancel disabled with the reason on another user's order without Manage Production Orders", async () => {
    rawState.controlTarget = makeOrder({ id: 12, status: 'queued', creator_id: 99 })
    rawState.canWrite = true

    const { wrapper } = await mountView()

    const cancel = wrapper.get('[data-testid="machine-control-cancel"]')
    expect(cancel.attributes('disabled')).toBeDefined()
    const span = cancel.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe(
      'Another user created this order, so canceling it needs the permission Manage Production Orders.',
    )
  })

  it("enables Cancel on another user's order with Manage Production Orders", async () => {
    rawState.controlTarget = makeOrder({ id: 13, status: 'queued', creator_id: 99 })
    rawState.canWrite = true

    const { wrapper } = await mountView([Permission.MANAGE_PRODUCTION_ORDERS])

    const cancel = wrapper.get('[data-testid="machine-control-cancel"]')
    expect(cancel.attributes('disabled')).toBeUndefined()
  })

  it('names the missing permission on a disabled Start through its span', async () => {
    rawState.controlTarget = makeOrder({ id: 14, status: 'queued' })
    rawState.canWrite = false
    rawState.controlStartBlocked = false

    const { wrapper } = await mountView()

    const start = wrapper.get('[data-testid="machine-control-start"]')
    expect(start.attributes('disabled')).toBeDefined()
    const span = start.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Production Orders.')
  })

  it('wires Start, Pause, Complete and Cancel through to the exposed handlers with the control target', async () => {
    const order = makeOrder({ id: 10, status: 'in_progress' })
    rawState.controlTarget = order
    rawState.canWrite = true
    rawState.controlStartBlocked = false
    rawState.controlCanOperateInspection = true

    const { wrapper } = await mountView()

    async function click(label: string): Promise<void> {
      const button = wrapper.findAll('button').find((b) => b.text() === label)
      expect(button).toBeTruthy()
      await button!.trigger('click')
    }

    await click('Pause')
    expect(onCardPauseMock).toHaveBeenCalledWith(order)

    await click('Complete')
    expect(onCardCompleteMock).toHaveBeenCalledWith(order)

    await click('Cancel')
    expect(onCardCancelMock).toHaveBeenCalledWith(order)
  })

  it('wires Start (queued) through to the exposed onCardStart handler with the control target', async () => {
    const queuedOrder = makeOrder({ id: 11, status: 'queued' })
    rawState.controlTarget = queuedOrder
    rawState.canWrite = true
    rawState.controlStartBlocked = false

    const { wrapper } = await mountView()
    const startButton = wrapper.findAll('button').find((b) => b.text() === 'Start')
    await startButton!.trigger('click')
    expect(onCardStartMock).toHaveBeenCalledWith(queuedOrder)
  })

  it('wires Resume (paused) through to the exposed onCardStart handler with the control target', async () => {
    const pausedOrder = makeOrder({ id: 12, status: 'paused' })
    rawState.controlTarget = pausedOrder
    rawState.canWrite = true
    rawState.controlStartBlocked = false

    const { wrapper } = await mountView()
    const resumeButton = wrapper.findAll('button').find((b) => b.text() === 'Resume')
    await resumeButton!.trigger('click')
    expect(onCardStartMock).toHaveBeenCalledWith(pausedOrder)
  })

  it('enables Open Item/Open Source Material/Open Order per their own disabled booleans and calls the exposed dialog openers', async () => {
    rawState.controlTarget = makeOrder({ id: 13, status: 'in_progress' })
    rawState.controlCanOpenItem = true
    rawState.controlCanOpenSourceItem = true

    const { wrapper } = await mountView()

    async function click(label: string): Promise<void> {
      const button = wrapper.findAll('button').find((b) => b.text() === label)
      expect(button!.attributes('disabled')).toBeUndefined()
      await button!.trigger('click')
    }

    await click('Open Item')
    expect(openItemDialogMock).toHaveBeenCalledTimes(1)

    await click('Open Source Material')
    expect(openSourceItemDialogMock).toHaveBeenCalledTimes(1)

    await click('Open Order')
    expect(openOrderDialogMock).toHaveBeenCalledTimes(1)
  })

  it('disables Open Item without controlCanOpenItem, and Open Source Material without controlCanOpenSourceItem, even with a control target', async () => {
    rawState.controlTarget = makeOrder({ id: 14, status: 'in_progress' })
    rawState.controlCanOpenItem = false
    rawState.controlCanOpenSourceItem = false

    const { wrapper } = await mountView()

    const itemButton = wrapper.findAll('button').find((b) => b.text() === 'Open Item')
    const sourceButton = wrapper.findAll('button').find((b) => b.text() === 'Open Source Material')
    const orderButton = wrapper.findAll('button').find((b) => b.text() === 'Open Order')

    expect(itemButton!.attributes('disabled')).toBeDefined()
    expect(sourceButton!.attributes('disabled')).toBeDefined()
    // Open Order only ever depends on there being a control target.
    expect(orderButton!.attributes('disabled')).toBeUndefined()
  })
})
