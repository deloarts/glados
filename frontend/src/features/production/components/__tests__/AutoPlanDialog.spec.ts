import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { Pinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'

import type {
  AutoPlanOrderDiffResponse,
  AutoPlanProgressEvent,
  AutoPlanRequest,
  AutoPlanResponse,
  AutoPlanRun,
  AutoPlanSkippedOrderResponse,
} from '../../types/scheduleBoardResponse'
import type { UserResponse } from '@/core/types/userResponse'

vi.mock('@/core/api', () => ({
  default: {
    // Blanket shape for every GET this dialog can trigger: machines/pools
    // (items/total, though those are normally served by the dedicated
    // production-machines mock below), adminSettingsStore.fetch(), which
    // the visible watcher actually reaches (see mountDialog) and reads
    // `.production.response_time_days` off unconditionally, and the
    // auto-plan run status endpoint (running/run), reached from
    // runStore.run()'s 409 handling and from the observer poll,
    // idle by default, overridden per-test with mockResolvedValueOnce.
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, production: { response_time_days: 1 }, running: false, run: null },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import api from '@/core/api'

vi.mock('@/features/production-machines', () => ({
  getProductionMachines: vi.fn<() => Promise<unknown>>().mockResolvedValue({ items: [], total: 0 }),
  getMachinePools: vi.fn<() => Promise<unknown>>().mockResolvedValue({ items: [], total: 0 }),
}))

type OnProgress = (ev: AutoPlanProgressEvent) => void

const emptyStreamResponse: AutoPlanResponse = {
  proposals: [],
  skipped_pinned_or_in_progress: 0,
  skipped_todays_planned: 0,
  skipped: [],
}

// onConfirm() goes through runStore.run() -> streamAutoPlanSchedule, so the
// stream module is mocked here. Resolves empty by default; tests that need
// progress frames or a specific outcome override per call with
// mockImplementationOnce/mockResolvedValueOnce/mockRejectedValueOnce.
const streamAutoPlanScheduleMock = vi
  .fn<(payload: AutoPlanRequest, onProgress: OnProgress, signal: AbortSignal) => Promise<AutoPlanResponse>>()
  .mockResolvedValue(emptyStreamResponse)

// The factory only references the mock inside the trampoline body (called at
// test time), never at factory-eval time. vi.mock factories are hoisted above
// this file's own top-level consts, so touching it earlier would be a TDZ error.
vi.mock('../../api/autoPlanScheduleStream', () => {
  class AutoPlanConnectionLostError extends Error {
    constructor() {
      super('Auto-plan stream ended without a result or error frame')
      this.name = 'AutoPlanConnectionLostError'
    }
  }
  return {
    streamAutoPlanSchedule: (payload: AutoPlanRequest, onProgress: OnProgress, signal: AbortSignal) =>
      streamAutoPlanScheduleMock(payload, onProgress, signal),
    AutoPlanConnectionLostError,
  }
})

import AutoPlanDialog from '../AutoPlanDialog.vue'
import { useAutoPlanRunStore } from '../../stores/autoPlanRunStore'
import { AutoPlanConnectionLostError } from '../../api/autoPlanScheduleStream'
import { SseHttpError } from '@/core/realtime/sseClient'

// The explain drawer is the shared handbook drawer, which links back to the
// doc's own page, so the dialog needs a router to mount.
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', name: 'Home', component: { template: '<div />' } },
    { path: '/handbook/:section/:page', name: 'HandbookPage', component: { template: '<div />' } },
  ],
})

// Both the Dialog and the explain Drawer teleport to <body>, so assertions
// query the document rather than the wrapper, and the mount has to be torn
// down explicitly or the previous test's markup is still there.
let wrapper: ReturnType<typeof mount> | null = null

// Mounts hidden, then flips `visible` true->false the same way a trigger
// button click does in production. AutoPlanDialog's whole attach/reset
// branch lives inside a `watch(visible, ...)` that only fires on an actual
// transition, never on the initial value. An optional shared `pinia` lets a
// test pre-populate runStore (e.g. start a run) before this dialog attaches
// to it.
async function mountDialog(pinia: Pinia = createPinia()) {
  await router.push('/')
  await router.isReady()

  wrapper = mountWithApp(AutoPlanDialog, {
    pinia,
    props: { visible: false },
    global: {
      plugins: [router],
    },
    attachTo: document.body,
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function deferred<T>(): {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason?: unknown) => void
} {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function makeResponse(overrides: Partial<AutoPlanResponse> = {}): AutoPlanResponse {
  return {
    proposals: [],
    skipped_pinned_or_in_progress: 0,
    skipped_todays_planned: 0,
    skipped: [],
    ...overrides,
  }
}

function orderDiff(overrides: Partial<AutoPlanOrderDiffResponse> = {}): AutoPlanOrderDiffResponse {
  return {
    order_id: 1,
    production_order_number: 'PO-1',
    lot_number: 'LOT-1',
    made_item_part_number: 'PN-1',
    made_item_revision: 'A',
    before_machine_id: null,
    after_machine_id: null,
    before_machine_pool_id: null,
    after_machine_pool_id: null,
    before_queue_sequence: 1,
    after_queue_sequence: 1,
    before_planned_start: null,
    before_planned_end: null,
    after_planned_start: null,
    after_planned_end: null,
    conflicts: [],
    ...overrides,
  }
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
})

function algorithmField(): HTMLElement {
  const select = document.querySelector('#autoplan-algorithm')
  expect(select).not.toBeNull()
  return select!.closest('.algorithm-select') as HTMLElement
}

function explainButton(): HTMLElement {
  const button = document.querySelector('.autoplan-header [aria-label="Explain"]')
  expect(button).not.toBeNull()
  return button as HTMLElement
}

function runButton(): HTMLButtonElement {
  const label = i18n.global.t('productionSchedule.autoPlan.run')
  const button = Array.from(document.querySelectorAll('[data-testid="autoplan-dialog-footer"] button')).find(
    (b) => b.textContent?.trim() === label,
  )
  expect(button).not.toBeUndefined()
  return button as HTMLButtonElement
}

function makeRun(overrides: Partial<AutoPlanRun> = {}): AutoPlanRun {
  return {
    run_id: 'run-1',
    user_id: 9,
    user_name: 'Other User',
    started_at: '2026-08-24T09:00:00Z',
    stage: 'placing',
    current: 2,
    total: 10,
    ...overrides,
  }
}

describe('AutoPlanDialog', () => {
  it('puts the explain button in the dialog header instead of a hint line', async () => {
    await mountDialog()

    // The per-algorithm blurb lives in the drawer.
    expect(algorithmField().querySelector('.field-hint')).toBeNull()

    const button = explainButton()
    // eslint-disable-next-line no-restricted-syntax -- asserts which icon the button shows
    expect(button.querySelector('.mdi-help')).not.toBeNull()
    // Same icon-only round shape as the close button it sits left of.
    expect(button.classList).toContain('p-button-rounded')
    expect(button.classList).toContain('p-button-text')
    expect(button.classList).toContain('p-button-icon-only')
    const header = button.closest('[data-testid="autoplan-dialog-header"]') as HTMLElement
    expect(header.querySelector('[aria-label="Close"]')).not.toBeNull()
  })

  it('labels both inputs of the algorithm row', async () => {
    await mountDialog()

    const labelFor = (id: string) =>
      document.querySelector(`.algorithm-select label[for="${id}"]`)?.textContent

    expect(labelFor('autoplan-algorithm')).toContain('Planning algorithm')
    expect(labelFor('autoplan-response-time-days')).toContain('Response time')
  })

  it('opens the auto-plan handbook doc from that button', async () => {
    await mountDialog()
    expect(document.querySelector('.handbook-drawer')).toBeNull()

    explainButton().click()
    await flushPromises()
    // The doc is a lazily-imported chunk, so wait for it rather than a tick.
    await vi.waitFor(() => {
      expect(document.querySelector('.handbook-prose')).not.toBeNull()
    })

    expect(document.querySelector('.handbook-drawer')).not.toBeNull()
    expect(document.body.textContent).toContain('How Auto-Plan works')
    expect(document.body.textContent).toContain('Reading the result')
    // Defaults to urgent_first, and the dialog passes that down as handbook
    // context, so that card is the highlighted one.
    expect(document.querySelector('.algorithm-card-current')?.textContent).toContain('Urgent First')
  })

  it('defaults the planning level to pools and offers both options', async () => {
    await mountDialog()

    const label = document.querySelector('label[for="autoplan-planning-level"]')
    expect(label?.textContent).toContain('Planning level')

    const selectButton = document.querySelector('#autoplan-planning-level')
    expect(selectButton).not.toBeNull()
    expect(selectButton!.textContent).toContain('Machines')
    expect(selectButton!.textContent).toContain('Pools')

    const vm = wrapper!.vm as unknown as { planningLevel: string }
    expect(vm.planningLevel).toBe('pools')
  })

  it('submits planning_level in the request payload and never assign_pool_machines, for both selections', async () => {
    const w = await mountDialog()

    const vm = w.vm as unknown as { planningLevel: string; onConfirm: () => Promise<void> }

    streamAutoPlanScheduleMock.mockClear()
    await vm.onConfirm()
    await flushPromises()

    expect(streamAutoPlanScheduleMock).toHaveBeenCalledTimes(1)
    let payload = streamAutoPlanScheduleMock.mock.calls[0]![0] as unknown as Record<string, unknown>
    expect(payload.planning_level).toBe('pools')
    expect(payload).not.toHaveProperty('assign_pool_machines')

    vm.planningLevel = 'machines'
    await flushPromises()
    streamAutoPlanScheduleMock.mockClear()
    await vm.onConfirm()
    await flushPromises()

    expect(streamAutoPlanScheduleMock).toHaveBeenCalledTimes(1)
    payload = streamAutoPlanScheduleMock.mock.calls[0]![0] as unknown as Record<string, unknown>
    expect(payload.planning_level).toBe('machines')
    expect(payload).not.toHaveProperty('assign_pool_machines')
  })

  it('renders a pool move in the results diff table', async () => {
    const w = await mountDialog()

    // Set the pool list directly rather than depending on the dialog's own
    // fetch (mocked to return no pools).
    const vm = w.vm as unknown as {
      pools: { id: number; name: string }[]
      onConfirm: () => Promise<void>
    }
    vm.pools = [
      { id: 5, name: 'Pool A' },
      { id: 9, name: 'Pool B' },
    ]

    streamAutoPlanScheduleMock.mockResolvedValueOnce({
      proposals: [
        {
          order_id: 1,
          production_order_number: 'PO-1',
          lot_number: 'LOT-1',
          made_item_part_number: 'PN-1',
          made_item_revision: 'A',
          before_machine_id: null,
          after_machine_id: null,
          before_machine_pool_id: 5,
          after_machine_pool_id: 9,
          before_queue_sequence: 1,
          after_queue_sequence: 1,
          before_planned_start: null,
          before_planned_end: null,
          after_planned_start: null,
          after_planned_end: null,
          conflicts: [],
        },
      ],
      skipped_pinned_or_in_progress: 0,
      skipped_todays_planned: 0,
      skipped: [],
    })

    await vm.onConfirm()
    await flushPromises()

    // Same "Pool: {name}" tag used everywhere else pool identity shows up
    // (see productionQueue.card.poolTag), rendered once for the before pool
    // and once for the after pool since they differ.
    expect(document.body.textContent).toContain('Pool: Pool A')
    expect(document.body.textContent).toContain('Pool: Pool B')
  })

  it('shows the running view immediately after Run - progress bar, no footer buttons, background hint, dialog still closable', async () => {
    const w = await mountDialog()
    const vm = w.vm as unknown as { onConfirm: () => Promise<void> }

    const { promise, resolve } = deferred<AutoPlanResponse>()
    streamAutoPlanScheduleMock.mockImplementationOnce(async () => promise)

    const confirmPromise = vm.onConfirm()
    await flushPromises()

    expect(document.querySelector('.autoplan-running')).not.toBeNull()
    expect(document.querySelector('[role="progressbar"]')).not.toBeNull()
    expect(document.body.textContent).toContain(
      'The run continues in the background if you close this dialog.',
    )
    // Footer has no buttons while running.
    expect(document.querySelector('[data-testid="autoplan-dialog-footer"]')?.children.length).toBe(0)
    // The Dialog's own close icon stays present. It stays closable during a
    // run; closing merely hides the view, the run keeps streaming
    // into the store.
    expect(document.querySelector('[aria-label="Close"]')).not.toBeNull()

    resolve(makeResponse())
    await confirmPromise
  })

  it('marks the running view stage and counter text as polite live regions', async () => {
    const w = await mountDialog()
    const vm = w.vm as unknown as { onConfirm: () => Promise<void> }

    const { promise, resolve } = deferred<AutoPlanResponse>()
    streamAutoPlanScheduleMock.mockImplementationOnce(async () => promise)

    const confirmPromise = vm.onConfirm()
    await flushPromises()

    const stageLabel = document.querySelector('.stage-label')
    expect(stageLabel?.getAttribute('role')).toBe('status')
    expect(stageLabel?.getAttribute('aria-live')).toBe('polite')

    resolve(makeResponse())
    await confirmPromise
  })

  it('populates the results table and emits applied exactly once when the run resolves', async () => {
    const w = await mountDialog()
    const vm = w.vm as unknown as { onConfirm: () => Promise<void> }

    streamAutoPlanScheduleMock.mockResolvedValueOnce(
      makeResponse({ proposals: [orderDiff({ production_order_number: 'PO-42' })] }),
    )

    await vm.onConfirm()
    await flushPromises()

    expect(document.querySelector('.autoplan-results')).not.toBeNull()
    expect(document.body.textContent).toContain('PO-42')
    expect(w.emitted('applied')).toHaveLength(1)
  })

  describe('skipped-orders list (results step)', () => {
    it('is hidden when no orders were skipped', async () => {
      const w = await mountDialog()
      const vm = w.vm as unknown as { onConfirm: () => Promise<void> }

      streamAutoPlanScheduleMock.mockResolvedValueOnce(makeResponse())

      await vm.onConfirm()
      await flushPromises()

      expect(document.querySelector('.autoplan-results')).not.toBeNull()
      expect(document.querySelector('.skipped-orders')).toBeNull()
    })

    it("renders each skipped order's number and translated reason label", async () => {
      const w = await mountDialog()
      const vm = w.vm as unknown as { onConfirm: () => Promise<void> }

      streamAutoPlanScheduleMock.mockResolvedValueOnce(
        makeResponse({
          skipped: [
            { order_id: 101, production_order_number: 'PO-101', reason: 'waiting_on_material' },
            { order_id: 102, production_order_number: 'PO-102', reason: 'no_eligible_machine' },
          ],
        }),
      )

      await vm.onConfirm()
      await flushPromises()

      const section = document.querySelector('.skipped-orders')
      expect(section).not.toBeNull()
      expect(section?.textContent).toContain('PO-101')
      expect(section?.textContent).toContain('Waiting on material')
      expect(section?.textContent).toContain('PO-102')
      expect(section?.textContent).toContain('No eligible machine')
    })

    it('falls back to the generic label for a reason string outside the known union', async () => {
      const w = await mountDialog()
      const vm = w.vm as unknown as { onConfirm: () => Promise<void> }

      const unknownReason = 'some_future_reason' as unknown as AutoPlanSkippedOrderResponse['reason']
      streamAutoPlanScheduleMock.mockResolvedValueOnce(
        makeResponse({
          skipped: [{ order_id: 201, production_order_number: 'PO-201', reason: unknownReason }],
        }),
      )

      await vm.onConfirm()
      await flushPromises()

      const section = document.querySelector('.skipped-orders')
      expect(section?.textContent).toContain('PO-201')
      expect(section?.textContent).toContain('Not placed')
    })
  })

  it('shows the confirm step with an error Message when the run rejects with a plain error, and does not emit applied', async () => {
    const w = await mountDialog()
    const vm = w.vm as unknown as { onConfirm: () => Promise<void> }

    streamAutoPlanScheduleMock.mockRejectedValueOnce(new Error('Auto-plan failed.'))

    await vm.onConfirm()
    await flushPromises()

    expect(document.querySelector('.autoplan-confirm')).not.toBeNull()
    const errorMessage = document.querySelector('[data-testid="autoplan-error-message"]')
    expect(errorMessage).not.toBeNull()
    expect(errorMessage?.textContent).toContain('Auto-plan failed.')
    expect(w.emitted('applied')).toBeUndefined()
  })

  it('shows the confirm step with a warn Message on connection loss, and does not emit applied', async () => {
    const w = await mountDialog()
    const vm = w.vm as unknown as { onConfirm: () => Promise<void> }

    streamAutoPlanScheduleMock.mockRejectedValueOnce(new AutoPlanConnectionLostError())

    await vm.onConfirm()
    await flushPromises()

    expect(document.querySelector('.autoplan-confirm')).not.toBeNull()
    const warnMessage = document.querySelector('[data-testid="autoplan-warn-message"]')
    expect(warnMessage).not.toBeNull()
    expect(warnMessage?.textContent).toContain('Connection lost')
    expect(w.emitted('applied')).toBeUndefined()
  })

  it('a dialog opened while the store is already running shows the running view immediately, and shows results + emits applied once the run it never started ends with a result', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const runStore = useAutoPlanRunStore()

    const { promise, resolve } = deferred<AutoPlanResponse>()
    streamAutoPlanScheduleMock.mockImplementationOnce(async () => promise)

    // Simulate a run started by another mounted instance of this dialog
    // (e.g. the other route's trigger), never through this instance's
    // onConfirm().
    const runPromise = runStore.run({} as AutoPlanRequest)
    expect(runStore.status).toBe('running')

    const w = await mountDialog(pinia)

    expect(document.querySelector('.autoplan-running')).not.toBeNull()
    expect(w.emitted('applied')).toBeUndefined()

    resolve(makeResponse({ proposals: [orderDiff({ production_order_number: 'PO-77' })] }))
    await runPromise
    await flushPromises()

    expect(document.querySelector('.autoplan-results')).not.toBeNull()
    expect(document.body.textContent).toContain('PO-77')
    expect(w.emitted('applied')).toHaveLength(1)
  })

  describe('observer view', () => {
    it('opening while another user has a run active shows the observer view with that user\'s name and no feed', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      useCurrentUserStore().user = { id: 1 } as unknown as UserResponse
      const runStore = useAutoPlanRunStore()
      runStore.activeRun = makeRun({ user_name: 'Other User' })

      await mountDialog(pinia)

      expect(document.querySelector('.autoplan-confirm')).toBeNull()
      expect(document.querySelector('.autoplan-observing')).not.toBeNull()
      expect(document.body.textContent).toContain('Other User')
      expect(document.querySelector('.autoplan-feed')).toBeNull()
    })

    it('marks the observer view stage text as a polite live region', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      useCurrentUserStore().user = { id: 1 } as unknown as UserResponse
      const runStore = useAutoPlanRunStore()
      runStore.activeRun = makeRun({ user_name: 'Other User' })

      await mountDialog(pinia)

      const stageLabel = document.querySelector('.autoplan-observing .stage-label')
      expect(stageLabel?.getAttribute('role')).toBe('status')
      expect(stageLabel?.getAttribute('aria-live')).toBe('polite')
    })

    it('the run ending while observing switches to the confirm step with an info Message naming who finished it', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      useCurrentUserStore().user = { id: 1 } as unknown as UserResponse
      const runStore = useAutoPlanRunStore()
      runStore.activeRun = makeRun({ user_name: 'Jane Finisher' })

      await mountDialog(pinia)
      expect(document.querySelector('.autoplan-observing')).not.toBeNull()

      runStore.activeRun = null
      await flushPromises()

      expect(document.querySelector('.autoplan-confirm')).not.toBeNull()
      const infoMessage = document.querySelector('[data-testid="autoplan-info-message"]')
      expect(infoMessage).not.toBeNull()
      expect(infoMessage?.textContent).toContain('Jane Finisher')
    })

    it('disables the Run button once another run becomes active while the dialog sits on the confirm step', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      useCurrentUserStore().user = { id: 1 } as unknown as UserResponse
      const runStore = useAutoPlanRunStore()

      const w = await mountDialog(pinia)
      // The mocked machine list is empty, so the Run button needs an
      // explicit selection to isolate this test from the unrelated
      // "no machines selected" disabled reason.
      const vm = w.vm as unknown as { selectedMachines: { id: number }[] }
      vm.selectedMachines = [{ id: 1 }]
      await flushPromises()

      expect(runButton().disabled).toBe(false)

      runStore.activeRun = makeRun({ user_id: 9 })
      await flushPromises()

      expect(runButton().disabled).toBe(true)
    })

    it('AutoPlanRunTakenError (409) switches from running straight to the observer view, with no error Message', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      useCurrentUserStore().user = { id: 1 } as unknown as UserResponse

      const w = await mountDialog(pinia)
      const vm = w.vm as unknown as { onConfirm: () => Promise<void> }

      const holderRun = makeRun({ user_id: 9, user_name: 'Winner' })
      vi.mocked(api.get).mockResolvedValueOnce({ data: { running: true, run: holderRun } })
      streamAutoPlanScheduleMock.mockRejectedValueOnce(new SseHttpError(409))

      await vm.onConfirm()
      await flushPromises()

      expect(document.querySelector('.autoplan-observing')).not.toBeNull()
      expect(document.body.textContent).toContain('Winner')
      expect(document.querySelector('[data-testid="autoplan-error-message"]')).toBeNull()
    })

    it('starts the 3s observer poll on entering the observing step and stops it on close', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      useCurrentUserStore().user = { id: 1 } as unknown as UserResponse
      const runStore = useAutoPlanRunStore()
      runStore.activeRun = makeRun()

      const startSpy = vi.spyOn(runStore, 'startObserverPolling')
      const stopSpy = vi.spyOn(runStore, 'stopObserverPolling')

      const w = await mountDialog(pinia)
      expect(document.querySelector('.autoplan-observing')).not.toBeNull()
      // Both the visible watcher's explicit start and the step watcher fire
      // on a first open; the store's start is idempotent, so the exact
      // count is irrelevant, only that it was started at all.
      const startCallsAfterOpen = startSpy.mock.calls.length
      expect(startCallsAfterOpen).toBeGreaterThanOrEqual(1)

      await w.setProps({ visible: false })
      await flushPromises()

      expect(stopSpy).toHaveBeenCalledTimes(1)

      // Reopening while the same run is still active: `step` is already
      // 'observing', so only an explicit start in the visible watcher can
      // bring the poll back.
      await w.setProps({ visible: true })
      await flushPromises()

      expect(document.querySelector('.autoplan-observing')).not.toBeNull()
      expect(startSpy.mock.calls.length).toBeGreaterThan(startCallsAfterOpen)
    })
  })
})
