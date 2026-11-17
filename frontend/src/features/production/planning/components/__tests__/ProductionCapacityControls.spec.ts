import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useAutoPlanRunStore } from '../../../stores/autoPlanRunStore'

import type { AutoPlanRun } from '../../../types/scheduleBoardResponse'

// Trigger-button state: with a run live in autoPlanRunStore, the
// Auto-Plan button in ProductionCapacityControls must show the spin icon
// while staying enabled, and clicking it must open AutoPlanDialog straight
// into its running view (it attaches, it never starts a second run). With
// the store idle, the button shows its normal icon and opens the confirm
// step instead. `LotsControls`' binding is a copy of this same one-liner;
// covered by type-check + review rather than a second heavyweight mount
// spec.

vi.mock('@/core/api', () => ({
  default: {
    // Blanket shape for every GET AutoPlanDialog (mounted inside the
    // Controls component) can trigger once opened: machines/pools
    // (items/total, though those are normally served by the dedicated
    // production-machines mock below) and adminSettingsStore.fetch(), which
    // reads `.production.response_time_days` off unconditionally.
    get: vi
      .fn<() => Promise<unknown>>()
      .mockResolvedValue({ data: { items: [], total: 0, production: { response_time_days: 1 } } }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

vi.mock('@/features/production-machines', () => ({
  getProductionMachines: vi.fn<() => Promise<unknown>>().mockResolvedValue({ items: [], total: 0 }),
  getMachinePools: vi.fn<() => Promise<unknown>>().mockResolvedValue({ items: [], total: 0 }),
}))

// The observer view starts the 3s status poll as soon as its dialog opens.
// It is mocked explicitly here (rather than relying on the blanket
// `@/core/api` mock above, which doesn't know this shape) so a poll can
// never reach the network even if a real timer fires mid-test.
const getAutoPlanRunStatusMock = vi
  .fn<() => Promise<{ running: boolean; run: null }>>()
  .mockResolvedValue({ running: false, run: null })

vi.mock('../../../api/getAutoPlanRunStatus', () => ({
  getAutoPlanRunStatus: () => getAutoPlanRunStatusMock(),
}))

import ProductionCapacityControls from '../ProductionCapacityControls.vue'

// AutoPlanDialog's explain drawer links back to its own handbook page, so it
// needs a router to mount, same as AutoPlanDialog.spec.ts.
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', name: 'Home', component: { template: '<div />' } },
    // No literal /production/capacity route exists in the real router
    // either; the Production tab view owns that path via its own
    // /production/:tab? catch-all. This stands in the same way here, just
    // to give HelpButton a real route.path to fall back on (see below).
    {
      path: '/production/capacity',
      name: 'ProductionCapacity',
      component: { template: '<div />' },
    },
    { path: '/handbook/:section/:page', name: 'HandbookPage', component: { template: '<div />' } },
  ],
})

async function mountControls(permissions: string[]) {
  await router.push('/')
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return mountWithApp(ProductionCapacityControls, {
    pinia,
    props: { dateRange: [new Date('2026-08-24'), new Date('2026-08-28')] },
    global: { plugins: [router], directives: { tooltip: Tooltip } },
    attachTo: document.body,
  })
}

// OpenVue's Button renders `disabled` as a plain DOM attribute rather than
// something Vue Test Utils' `.props()`/`.attributes()` reflects reliably
// here (both come back empty even when the rendered button clearly has
// `disabled=""` and `data-p-disabled="true"`), so assertions below read the
// real DOM element instead of the component wrapper.
function autoPlanButtonEl(): HTMLButtonElement {
  const el = document.querySelector(
    `[aria-label="${i18n.global.t('productionSchedule.autoPlan.trigger')}"]`,
  )
  expect(el).not.toBeNull()
  return el as HTMLButtonElement
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ProductionCapacityControls', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows the normal icon and opens the confirm step when the store is idle', async () => {
    const wrapper = await mountControls(['write:production_orders'])
    await flushPromises()

    const button = autoPlanButtonEl()
    // eslint-disable-next-line no-restricted-syntax -- asserts which icon the button shows
    expect(button.querySelector('.mdi-calendar-sync')).not.toBeNull()
    // eslint-disable-next-line no-restricted-syntax -- asserts which icon the button shows
    expect(button.querySelector('.mdi-loading')).toBeNull()
    expect(button.disabled).toBe(false)

    button.click()
    await flushPromises()

    expect(document.querySelector('.autoplan-confirm')).not.toBeNull()
    expect(document.querySelector('.autoplan-running')).toBeNull()

    wrapper.unmount()
  })

  it('shows the spin icon and stays enabled while a run is live, and clicking it attaches to the running view', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = userWithPermissions(['write:production_orders'])
    useAutoPlanRunStore().status = 'running'

    await router.push('/')
    await router.isReady()

    const wrapper = mountWithApp(ProductionCapacityControls, {
      pinia,
      props: { dateRange: [new Date('2026-08-24'), new Date('2026-08-28')] },
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await flushPromises()

    const button = autoPlanButtonEl()
    // eslint-disable-next-line no-restricted-syntax -- asserts which icon the button shows
    expect(button.querySelector('.mdi-loading.mdi-spin')).not.toBeNull()
    expect(button.disabled).toBe(false)

    button.click()
    await flushPromises()

    // Attaches to the already-running view; it never starts a second run
    // (no confirm form shown).
    expect(document.querySelector('.autoplan-running')).not.toBeNull()
    expect(document.querySelector('.autoplan-confirm')).toBeNull()

    wrapper.unmount()
  })

  it('spins for a run started by ANOTHER user too, and clicking it opens the observer view', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    // userWithPermissions always seeds id: 1. The active run below belongs to someone
    // else, so isMine is false and anyRunActive alone drives the spin.
    useCurrentUserStore().user = userWithPermissions(['write:production_orders'])
    const otherUsersRun: AutoPlanRun = {
      run_id: 'run-1',
      user_id: 99,
      user_name: 'Other User',
      started_at: '2026-08-24T09:00:00Z',
      stage: 'placing',
      current: 1,
      total: 5,
    }
    useAutoPlanRunStore().activeRun = otherUsersRun

    await router.push('/')
    await router.isReady()

    const wrapper = mountWithApp(ProductionCapacityControls, {
      pinia,
      props: { dateRange: [new Date('2026-08-24'), new Date('2026-08-28')] },
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await flushPromises()

    const button = autoPlanButtonEl()
    // eslint-disable-next-line no-restricted-syntax -- asserts which icon the button shows
    expect(button.querySelector('.mdi-loading.mdi-spin')).not.toBeNull()
    expect(button.disabled).toBe(false)

    button.click()
    await flushPromises()

    // Someone else's run opens the observer view, not the confirm form or
    // the runner's own running view.
    expect(document.querySelector('.autoplan-observing')).not.toBeNull()
    expect(document.querySelector('.autoplan-running')).toBeNull()
    expect(document.querySelector('.autoplan-confirm')).toBeNull()
    expect(document.body.textContent).toContain('Other User')

    wrapper.unmount()
  })

  it('disables the button without write:production_orders, regardless of run state', async () => {
    const wrapper = await mountControls([])
    await flushPromises()

    expect(autoPlanButtonEl().disabled).toBe(true)
    // A disabled button fires no mouse events, so its span names the permission.
    const span = autoPlanButtonEl().parentElement as
      | (HTMLElement & { $_ptooltipValue?: string })
      | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Production Orders.')

    wrapper.unmount()
  })

  // HelpButton (dropped in with no explicit slug, same as LotsControls'
  // own copy of this one-liner) infers its doc from route.path when nothing
  // declares one; see HelpButton.spec.ts's "falls back to the route
  // path" case. There is no dedicated /production/capacity route (the
  // Production tab view owns that path via its own /production/:tab?
  // catch-all), so this is what actually makes the button appear on the
  // real Capacity tab: the URL segments alone have to resolve to the
  // production/capacity doc.
  it('shows a handbook button that opens the Capacity doc, resolved from the route path alone', async () => {
    await router.push('/production/capacity')
    await router.isReady()

    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = userWithPermissions(['write:production_orders'])

    const wrapper = mountWithApp(ProductionCapacityControls, {
      pinia,
      props: { dateRange: [new Date('2026-08-24'), new Date('2026-08-28')] },
      global: { plugins: [router], directives: { tooltip: Tooltip } },
      attachTo: document.body,
    })
    await flushPromises()

    const handbookButton = document.querySelector(
      `[aria-label="${i18n.global.t('handbook.tooltip')}"]`,
    ) as HTMLButtonElement | null
    expect(handbookButton).not.toBeNull()

    handbookButton!.click()
    await flushPromises()
    await vi.waitFor(() => {
      expect(document.querySelector('.handbook-prose')).not.toBeNull()
    })
    expect(document.body.textContent).toContain('Why is a slot free?')

    wrapper.unmount()
    await router.push('/')
  })
})
