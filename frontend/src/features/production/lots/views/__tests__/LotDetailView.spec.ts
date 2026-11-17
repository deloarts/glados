import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotResponse, makeTestRouter } from '@/test-utils/factories'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import type { LotResponse } from '../../../types/productionLotsResponse'
import type { LotStateSignal } from '../../utils/lotStateSummary'

// LotDetailContent owns the whole record (permissions, live refresh, a dozen
// nested dialogs); none of that is this view's concern, so it's replaced
// with a stub that exposes exactly the contract LotDetailView reads
// (LotDetailView.vue's defineExpose block), driven by a shared `rawState`
// the tests mutate directly before mounting.
//
// Only plain data + vi.fn() spies live inside vi.hoisted, since its factory
// runs before ANY import (including this file's own `import ... from 'vue'`)
// is evaluated, so nothing from 'vue' can be referenced in there. The mock
// factory below has the same problem one level up: real ESM import
// declarations, including `import LotDetailView from '../LotDetailView.vue'`
// further down this file, resolve before any of this file's own top-level
// statements run, so a plain top-level `const state = reactive(...)` would
// already be in its temporal dead zone by the time the factory (invoked
// while resolving LotDetailView's own import of LotDetailContent.vue) tries
// to read it. A dynamic `import('vue')` inside the factory sidesteps both:
// it resolves the real module on demand rather than through this file's own
// (not-yet-executed) binding.
const {
  rawState,
  printLotMock,
  toggleManageMock,
  openHoldMock,
  resumeLotMock,
  openForceStatusMock,
  reloadMock,
} = vi.hoisted(() => ({
  rawState: {
    lot: null as LotResponse | null,
    loading: false,
    stateSignals: [] as LotStateSignal[],
    canWrite: true,
    canManage: true,
    canPrint: true,
    manageMode: false,
  },
  printLotMock: vi.fn<(classifier: string) => void>(),
  toggleManageMock: vi.fn<() => void>(),
  openHoldMock: vi.fn<() => void>(),
  resumeLotMock: vi.fn<() => void>(),
  openForceStatusMock: vi.fn<(action: 'complete' | 'cancel') => void>(),
  reloadMock: vi.fn<() => void>(),
}))

vi.mock('../../components/LotDetailContent.vue', async () => {
  const { defineComponent, h, reactive, toRefs } = await import('vue')
  const state = reactive(rawState)

  const ContentStub = defineComponent({
    name: 'LotDetailContent',
    props: { lotId: Number, variant: String },
    setup(_, { expose }) {
      expose({
        ...toRefs(state),
        printLot: printLotMock,
        isPrinting: () => false,
        toggleManage: toggleManageMock,
        openHold: openHoldMock,
        resumeLot: resumeLotMock,
        openForceStatus: openForceStatusMock,
        reload: reloadMock,
      })
      return () => h('div', { class: 'lot-detail-content-stub' })
    },
  })

  return { default: ContentStub }
})

import LotDetailView from '../LotDetailView.vue'
import { lotActions } from '../../__tests__/fixtures'

vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

// The actions default to what the backend offers a manager of lots on a lot
// in that status that produced its four pieces.
function makeLot(overrides: Partial<LotResponse> = {}): LotResponse {
  return makeLotResponse({
    actions: lotActions(overrides.status ?? 'in_progress', 4),
    id: 42,
    public_id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
    created: '2026-07-01T09:00:00',
    lot_number: 'LOT-0042',
    ...overrides,
  })
}

/**
 * Mirrors the real route, constraint included, so the view reads its id the
 * same way it does in the app.
 */
function makeRouter() {
  return makeTestRouter([
    { path: '/production/lots/:id(\\d+)', name: 'LotDetail', component: LotDetailView },
  ])
}

// Every mounted view watches the same module-level useLotDetail() singleton,
// so a view left mounted by an earlier test would still react to a later
// test toggling it, so tear them down between tests.
const mounted: VueWrapper[] = []

async function mountView() {
  const router = makeRouter()
  await router.push('/production/lots/42')
  await router.isReady()

  const wrapper = mountWithApp(LotDetailView, {
    global: {
      plugins: [router, ConfirmationService],
      directives: { tooltip: Tooltip },
    },
  })
  mounted.push(wrapper)
  await flushPromises()
  return { wrapper, router }
}

describe('LotDetailView', () => {
  afterEach(() => {
    for (const wrapper of mounted) wrapper.unmount()
    mounted.length = 0
  })

  beforeEach(() => {
    Object.assign(rawState, {
      lot: makeLot({ status: 'in_progress' }),
      loading: false,
      stateSignals: [],
      canWrite: true,
      canManage: true,
      canPrint: true,
      manageMode: false,
    })
    printLotMock.mockReset()
    toggleManageMock.mockReset()
    openHoldMock.mockReset()
    resumeLotMock.mockReset()
    openForceStatusMock.mockReset()
    reloadMock.mockReset()
  })

  it('passes the numeric route id and the page variant to LotDetailContent', async () => {
    const { wrapper } = await mountView()

    const stub = wrapper.findComponent({ name: 'LotDetailContent' })
    expect(stub.props('lotId')).toBe(42)
    expect(stub.props('variant')).toBe('page')
  })

  it('shows the lot number, status tag, item, and a state-signal tag in the InfoBar', async () => {
    rawState.lot = makeLot({
      lot_number: 'LOT-0042',
      status: 'in_progress',
      made_item_article_name: 'Bracket',
      made_item_part_number: 'PN-1',
    })
    rawState.stateSignals = [
      {
        id: 'onTrack',
        labelKey: 'production.lots.detail.state.onTrack',
        severity: 'success',
        icon: 'mdi mdi-check-circle-outline',
      },
    ]

    const { wrapper } = await mountView()
    const text = wrapper.text()

    expect(text).toContain('LOT-0042')
    expect(text).toContain('In Progress')
    expect(text).toContain('Bracket')
    expect(text).toContain('PN-1')
    expect(text.indexOf('PN-1')).toBeLessThan(text.indexOf('Bracket'))
    expect(text).toContain('On track')
  })

  it('reloads the record when the app-wide lot dialog closes over the page', async () => {
    const { visible } = useLotDetail()
    visible.value = false
    await mountView()
    expect(reloadMock).not.toHaveBeenCalled()

    visible.value = true
    await flushPromises()
    expect(reloadMock).not.toHaveBeenCalled()

    visible.value = false
    await flushPromises()
    expect(reloadMock).toHaveBeenCalledTimes(1)
  })

  it('the back button navigates to the lots list', async () => {
    const { wrapper, router } = await mountView()

    const backButton = wrapper.findAll('button').find((b) => b.text() === 'Back to Lots')
    expect(backButton).toBeTruthy()
    await backButton!.trigger('click')
    // trigger() only flushes Vue's own reactivity queue; router.push() runs
    // its navigation as a separate async task that needs its own await.
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/production/lots')
  })

  it('wires the record actions through to the exposed LotDetailContent methods', async () => {
    const { wrapper } = await mountView()

    async function click(label: string): Promise<void> {
      const button = wrapper.findAll('button').find((b) => b.text() === label)
      expect(button).toBeTruthy()
      await button!.trigger('click')
    }

    await click('Print Docket')
    expect(printLotMock).toHaveBeenCalledWith('lot_docket')

    await click('Manage')
    expect(toggleManageMock).toHaveBeenCalledTimes(1)

    await click('Put on Hold')
    expect(openHoldMock).toHaveBeenCalledTimes(1)

    await click('Complete Lot')
    expect(openForceStatusMock).toHaveBeenCalledWith('complete')

    await click('Cancel Lot')
    expect(openForceStatusMock).toHaveBeenCalledWith('cancel')
  })

  it('on_hold status: offers Resume instead of Hold', async () => {
    rawState.lot = makeLot({ status: 'on_hold' })
    const { wrapper } = await mountView()

    expect(wrapper.findAll('button').find((b) => b.text() === 'Put on Hold')).toBeFalsy()

    const resumeButton = wrapper.findAll('button').find((b) => b.text() === 'Resume')
    expect(resumeButton).toBeTruthy()
    await resumeButton!.trigger('click')

    expect(resumeLotMock).toHaveBeenCalledTimes(1)
  })

  it('completed status: hides Hold, Resume, Complete and Cancel', async () => {
    rawState.lot = makeLot({ status: 'completed' })
    const { wrapper } = await mountView()

    const labels = wrapper.findAll('button').map((b) => b.text())
    expect(labels).not.toContain('Put on Hold')
    expect(labels).not.toContain('Resume')
    expect(labels).not.toContain('Complete Lot')
    expect(labels).not.toContain('Cancel Lot')
  })

  it('hides Complete/Cancel when the lot does not offer them, as to a non-manager', async () => {
    rawState.canManage = false
    rawState.lot = makeLot({ actions: ['hold', 'scrap', 'edit_structure', 'reorder_positions'] })
    const { wrapper } = await mountView()

    const labels = wrapper.findAll('button').map((b) => b.text())
    expect(labels).not.toContain('Complete Lot')
    expect(labels).not.toContain('Cancel Lot')
    expect(labels).toContain('Put on Hold')
  })

  it('disables Manage and Hold without canWrite, naming the missing permission', async () => {
    rawState.canWrite = false
    const { wrapper } = await mountView()

    const manage = wrapper.get('[data-testid="lot-manage-toggle"]')
    expect(manage.attributes('disabled')).toBeDefined()
    const span = manage.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Production Lots.')

    const holdButton = wrapper.findAll('button').find((b) => b.text() === 'Put on Hold')
    expect(holdButton?.attributes('disabled')).toBeDefined()
  })

  it('ViewsBar sync calls reload, and reflects the content loading state', async () => {
    const { wrapper } = await mountView()

    const syncButton = wrapper.findAll('button').find((b) => b.text() === 'Sync')
    expect(syncButton).toBeTruthy()
    expect(syncButton!.classes()).not.toContain('p-button-loading')

    await syncButton!.trigger('click')
    expect(reloadMock).toHaveBeenCalledTimes(1)
  })

  it('shows the sync button as loading while LotDetailContent is loading', async () => {
    rawState.loading = true
    const { wrapper } = await mountView()

    const syncButton = wrapper.findAll('button').find((b) => b.text() === 'Sync')
    expect(syncButton!.classes()).toContain('p-button-loading')
  })

  it('mounts no ConfirmDialog of its own, since App.vue hosts the one every confirmation uses', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.findComponent({ name: 'ConfirmDialog' }).exists()).toBe(false)
  })
})
