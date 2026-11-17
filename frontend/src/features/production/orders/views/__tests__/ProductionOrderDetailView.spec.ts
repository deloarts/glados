import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'
import { AxiosError } from 'axios'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { RouteStub, makeTestRouter } from '@/test-utils/factories'

const getProductionOrderMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('../../../lots/api/getProductionOrder', () => ({
  getProductionOrder: (...args: unknown[]) => getProductionOrderMock(...args),
}))

import ProductionOrderDetailView from '../ProductionOrderDetailView.vue'

function makeOrder(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    public_id: 'aaaaaaaa-0000-0000-0000-000000000001',
    created: '2026-01-01',
    changed: null,
    production_order_number: 'PO-1',
    status: 'queued',
    priority: 'normal',
    pinned: false,
    queue_sequence: 1,
    quantity: 10,
    quantity_completed: 0,
    estimated_duration_minutes: 30,
    note: null,
    planned_start: null,
    planned_end: null,
    not_before: null,
    actual_start: null,
    actual_end: null,
    creator_id: 1,
    creator: null,
    planned_by_id: null,
    planned_by: null,
    machine_id: null,
    machine_internal_name: '',
    lot_position_id: 1,
    lot_id: 7,
    lot_number: 'L-7',
    made_item_part_number: 'MI-1',
    ...overrides,
  }
}

function notFoundError() {
  const error = new AxiosError('Not Found')
  error.response = { status: 404 } as AxiosError['response']
  return error
}

function makeRouter() {
  return makeTestRouter([
    {
      path: '/production/orders/:id(\\d+)',
      name: 'ProductionOrderDetail',
      component: ProductionOrderDetailView,
    },
    { path: '/production/queue', component: RouteStub },
    { path: '/production/lots/:id(\\d+)', component: RouteStub },
  ])
}

const mounted: VueWrapper[] = []

async function mountView(id = '1') {
  const pinia = createPinia()
  setActivePinia(pinia)

  const router = makeRouter()
  await router.push(`/production/orders/${id}`)
  await router.isReady()

  const wrapper = mountWithApp(ProductionOrderDetailView, {
    pinia,
    global: {
      plugins: [router, ConfirmationService],
      directives: { tooltip: Tooltip },
    },
  })
  mounted.push(wrapper)
  await flushPromises()
  await flushPromises()
  return { wrapper, router }
}

describe('ProductionOrderDetailView', () => {
  beforeEach(() => {
    getProductionOrderMock.mockReset()
    getProductionOrderMock.mockResolvedValue(makeOrder())
  })

  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('shows the info bar with the production order number', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder({ production_order_number: 'PO-42' }))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('PO-42')
    expect(wrapper.text()).toContain('Queued')
  })

  it('shows the not-found screen on a 404', async () => {
    getProductionOrderMock.mockRejectedValue(notFoundError())

    const { wrapper } = await mountView('999')

    expect(wrapper.text()).toContain('This production order does not exist.')
  })

  it('shows the load-error screen on a non-404 error', async () => {
    getProductionOrderMock.mockRejectedValue(new Error('network down'))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('The production order could not be loaded.')
  })

  it('navigates back to the queue', async () => {
    const { wrapper, router } = await mountView()

    const back = wrapper.findAll('button').find((b) => b.text() === 'Back to Queue')
    expect(back).toBeTruthy()
    await back!.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/production/queue')
  })

  it('links to the order\'s lot', async () => {
    getProductionOrderMock.mockResolvedValue(makeOrder({ lot_id: 55, lot_number: 'L-55' }))

    const { wrapper } = await mountView()

    const lotLink = wrapper.findAll('a').find((a) => a.text().includes('L-55'))
    expect(lotLink).toBeTruthy()
    expect(lotLink!.attributes('href')).toBe('/production/lots/55')
  })
})
