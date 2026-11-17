import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

import { useProductionLotsFiltersStore } from '../../stores/productionLotsFiltersStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { makeUserResponse } from '@/test-utils/factories'
import { useLotDetail } from '@/shared/composables/useLotDetail'

// Same harness ProductionLotsListView.spec.ts's own "needs-assignment
// filter" describe block uses, duplicated (not imported) since that file's
// mountView and getMock are module-local and the file itself is
// read-only.

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
  return { wrapper }
}

function lastLotsParams(): Record<string, unknown> | undefined {
  const calls = getMock.mock.calls.filter(([url]) => url === '/production-lots/')
  return calls.at(-1)?.[1]?.params
}

describe('ProductionLotsListView needs-approval filter', () => {
  beforeEach(async () => {
    getMock.mockReset()
    getMock.mockImplementation(() =>
      Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } }),
    )
    await router.push('/')
    useLotDetail().visible.value = false
    useLotDetail().lotId.value = null
  })

  it('is off by default and sends no source_approval_status param', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    expect(useProductionLotsFiltersStore().needsApprovalOnly).toBe(false)
    expect(lastLotsParams()).not.toHaveProperty('source_approval_status')

    wrapper.unmount()
  })

  it('sends source_approval_status=pending when toggled on', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    useProductionLotsFiltersStore().toggleNeedsApprovalOnly()
    await flushPromises()

    expect(lastLotsParams()).toMatchObject({ source_approval_status: 'pending' })

    wrapper.unmount()
  })

  it('drops the param again when toggled back off', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    const filtersStore = useProductionLotsFiltersStore()
    filtersStore.toggleNeedsApprovalOnly()
    await flushPromises()
    expect(lastLotsParams()).toMatchObject({ source_approval_status: 'pending' })

    filtersStore.toggleNeedsApprovalOnly()
    await flushPromises()
    expect(lastLotsParams()).not.toHaveProperty('source_approval_status')

    wrapper.unmount()
  })

  it('toggling refetches the lots list', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    const callsBefore = getMock.mock.calls.filter(([url]) => url === '/production-lots/').length

    useProductionLotsFiltersStore().toggleNeedsApprovalOnly()
    await flushPromises()

    const callsAfter = getMock.mock.calls.filter(([url]) => url === '/production-lots/').length
    expect(callsAfter).toBeGreaterThan(callsBefore)

    wrapper.unmount()
  })

  it('combines independently with needsAssignmentOnly - both params sent together', async () => {
    const { wrapper } = mountView()
    await flushPromises()
    await flushPromises()

    const filtersStore = useProductionLotsFiltersStore()
    filtersStore.toggleNeedsAssignmentOnly()
    await flushPromises()
    filtersStore.toggleNeedsApprovalOnly()
    await flushPromises()

    expect(lastLotsParams()).toMatchObject({
      statuses: ['draft', 'partially_planned'],
      source_approval_status: 'pending',
    })

    wrapper.unmount()
  })
})
