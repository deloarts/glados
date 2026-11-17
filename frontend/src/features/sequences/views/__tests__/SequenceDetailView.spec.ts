import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { controlledDocumentFields } from '@/test-utils/controlledDocument'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { ProductDevice } from '@/features/product-devices'
import type { SequenceResponse, SequenceUpdateRequest } from '../../types/sequence'

// The date cells load the user list for the actor's card; it stays empty
// here so the request never reaches the network.
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: async () => ({ items: [], total: 0, limit: 0, skip: 0 }),
}))
// The device dialog lists the device's calculations. Unmocked, jsdom sends
// the request to its own origin, http://localhost:3000, where a running dev
// backend answers 401 during a later test and ends that test's session.
vi.mock('@/features/tools/api/getCalculations', () => ({
  getCalculations: async () => ({ items: [], total: 0, limit: 200, skip: 0 }),
}))

const sequences = new Map<number, SequenceResponse>()
const updateSequence = vi.fn<(id: number, body: SequenceUpdateRequest) => Promise<SequenceResponse>>()
const lockSequence = vi.fn<(id: number, takeOver: boolean) => Promise<SequenceResponse>>()

vi.mock('../../api/sequencesApi', () => ({
  getSequence: async (id: number) => {
    const found = sequences.get(id)
    if (!found) throw new Error('not found')
    return found
  },
  getSequenceRevisions: async (id: number) => [sequences.get(id)],
  updateSequence: (id: number, body: SequenceUpdateRequest) => updateSequence(id, body),
  lockSequence: (id: number, takeOver: boolean) => lockSequence(id, takeOver),
  unlockSequence: async (id: number) => sequences.get(id),
  releaseSequence: vi.fn<() => Promise<void>>(),
  reviseSequence: vi.fn<() => Promise<void>>(),
  markSequenceInvalid: vi.fn<() => Promise<void>>(),
  deleteSequence: vi.fn<() => Promise<void>>(),
}))
vi.mock('../../api/productVariantsApi', () => ({ getProductVariants: async () => [] }))
vi.mock('../../api/productApi', () => ({
  getSequenceProduct: async () => ({ id: 3, archived: false, designated_user_id: 1, contains_pneumatics: true }),
}))
const productDevices = vi.fn<() => Promise<ProductDevice[]>>(async () => [])
vi.mock('@/features/product-devices/api/productDevicesApi', () => ({ getProductDevices: () => productDevices() }))
vi.mock('@/features/product-devices/api/productDeviceResourcesApi', () => ({
  getProductDeviceOptions: () => Promise.resolve([]),
  getProductDeviceKinds: () => Promise.resolve([]),
}))

import SequenceDetailView from '../SequenceDetailView.vue'

function sequence(overrides: Partial<SequenceResponse> = {}): SequenceResponse {
  return {
    ...controlledDocumentFields(),
    id: 4,
    public_id: '11111111-1111-1111-1111-111111111114',
    created: '2026-10-23T08:00:00Z',
    changed: '2026-10-23T08:00:00Z',
    document_number: 'SEQ-26-0004',
    creator_id: 1,
    creator_full_name: 'Author',
    product_id: 3,
    product_number: 'M26001',
    name: 'Automatic',
    step_count: 0,
    steps: [],
    frozen: null,
    changes: [],
    ...overrides,
  }
}

async function mountView(permissions: string[] = ['write:sequences', 'release:sequences']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { id: 1, permissions, is_systemuser: false } as never
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/workspace/products/:id(\\d+)/sequences/:sequenceId(\\d+)/:view(initial|diagram|grafcet)?',
        name: 'SequenceDetail',
        component: SequenceDetailView,
      },
      { path: '/workspace/products/:id(\\d+)/:tab?', name: 'ProductDetail', component: { template: '<div />' } },
    ],
  })
  await router.push('/workspace/products/3/sequences/4')
  const Host = defineComponent({ render: () => h(RouterView) })
  const wrapper = mountWithApp(Host, {
    pinia,
    global: { plugins: [router, ConfirmationService], directives: { tooltip: Tooltip } },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('SequenceDetailView', () => {
  beforeEach(() => {
    localStorage.clear()
    sequences.clear()
    sequences.set(4, sequence())
    lockSequence.mockReset()
    lockSequence.mockImplementation(async (id) => {
      const locked = { ...sequences.get(id)!, locked_by_id: 1, locked_by_full_name: 'Author', locked_at: '2026-10-23T09:00:00Z', lock_expires_at: '2099-01-01T00:00:00Z' }
      sequences.set(id, locked)
      return locked
    })
    updateSequence.mockReset()
    updateSequence.mockImplementation(async (id, body) => {
      const saved = { ...sequences.get(id)!, name: body.name, steps: body.steps, step_count: body.steps.length }
      sequences.set(id, saved)
      return saved
    })
  })

  it('edits under the lock and saves the steps', async () => {
    const { wrapper } = await mountView()
    expect(wrapper.text()).toContain('SEQ-26-0004')
    expect(wrapper.find('[data-testid="sequence-add-step"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sequence-release"]').attributes('disabled')).toBeDefined()

    await wrapper.find('[data-testid="sequence-edit"]').trigger('click')
    await flushPromises()
    expect(lockSequence).toHaveBeenCalledWith(4, false)

    await wrapper.find('[data-testid="sequence-add-step"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="sequence-save"]').trigger('click')
    await flushPromises()

    expect(updateSequence).toHaveBeenCalledTimes(1)
    const body = updateSequence.mock.calls[0]![1]
    expect(body.name).toBe('Automatic')
    expect(body.steps).toHaveLength(1)
    expect(body.steps[0]!.transitions![0]!.target).toBe('end')
    wrapper.unmount()
  })

  it('switches views through the address and back to the steps, keeping unsaved changes', async () => {
    const { wrapper, router } = await mountView()
    await wrapper.find('[data-testid="sequence-edit"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="sequence-add-step"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="sequence-view-grafcet"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.params.view).toBe('grafcet')
    expect(wrapper.find('[data-testid="sequence-grafcet"]').exists()).toBe(true)

    await wrapper.find('[data-testid="sequence-view-editor"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/workspace/products/3/sequences/4')
    expect(wrapper.findAll('[data-testid="sequence-step-1"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('shows the start state as a view of its own in the views bar', async () => {
    const { wrapper, router } = await mountView()
    const views = wrapper.find('[data-testid="sequence-views"]')
    expect(views.find('[data-testid="sequence-variant"]').text()).toContain('All variants')
    expect(wrapper.find('[data-testid="sequence-controls"] [data-testid="sequence-view-editor"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sequence-start-state"]').exists()).toBe(false)

    await views.find('[data-testid="sequence-view-initial"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.params.view).toBe('initial')
    expect(wrapper.find('[data-testid="sequence-start-state"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it("goes back to the product's sequences", async () => {
    const { wrapper, router } = await mountView()
    await wrapper.find('[data-testid="sequence-back"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/workspace/products/3/sequences')
    wrapper.unmount()
  })

  it('opens a device of the start state in its dialog', async () => {
    productDevices.mockResolvedValueOnce([
      {
        edit_version: 0,
        id: 5,
        public_id: 'd',
        created: '2026-10-22T00:00:00Z',
        changed: '2026-10-22T00:00:00Z',
        changed_by: null,
        changed_by_id: null,
        archived: false,
        product_id: 3,
        product_number: 'M26001',
        location: 'B01',
        name: 'Lift',
        driving_medium_id: 7,
        driving_medium_letter: 'P',
        number: 1,
        name_utf8: 'B01 Lift P1',
        name_ascii: 'B01_Lift_P1',
        full_name_utf8: 'M26001 B01 Lift P1',
        full_name_ascii: 'M26001_B01_Lift_P1',
        kind_id: 1,
        description: null,
        initial_position_id: null,
        initial_position_value: null,
        energy_loss_behaviour_id: null,
        energy_restoration_behaviour_id: null,
        monitoring_time_ms: null,
        driven_by_id: null,
        driven_position_map: {},
        safety_relevant: false,
        parameters: {},
        position_labels: {},
        travel_times_ms: {},
        rendering_file_id: null,
        assembly_file_id: null,
        marker_x: null,
        marker_y: null,
        creator_id: 1,
        creator: null,
        components: [],
      },
    ])
    const { wrapper, router } = await mountView()
    await router.push('/workspace/products/3/sequences/4/initial')
    await flushPromises()
    const row = wrapper.find('[data-testid="sequence-start-state"] tbody tr')
    expect(row.text()).toContain('B01 Lift P1')
    await row.trigger('click')
    await flushPromises()
    expect(document.body.querySelector('[data-testid="product-device-dialog"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('shows the actions without the rights for them disabled, not hidden', async () => {
    const { wrapper } = await mountView([])
    expect(wrapper.find('[data-testid="sequence-edit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid="sequence-release"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid="sequence-delete"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it("disables Edit of another user's draft without manage:sequences", async () => {
    sequences.set(4, sequence({ creator_id: 2, creator_full_name: 'Other' }))
    const { wrapper } = await mountView(['write:sequences'])
    expect(wrapper.find('[data-testid="sequence-edit"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('shows a released revision read-only without Edit', async () => {
    sequences.set(4, sequence({ released_at: '2026-10-23T10:00:00Z', read_only: true, released_by_full_name: 'Author' }))
    const { wrapper } = await mountView()
    expect(wrapper.find('[data-testid="sequence-edit"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sequence-revise"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-testid="sequence-mark-invalid"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('shows the GRAFCET beside the editor on a wide screen only', async () => {
    // Only the page's own query answers true; OpenVue asks about its own
    // breakpoints too, so everything else keeps the setup's stub.
    const original = window.matchMedia
    vi.stubGlobal('matchMedia', (query: string) => ({
      ...(original(query) as object),
      matches: query === '(min-width: 1400px)',
    }))
    try {
      const { wrapper, router } = await mountView()
      expect(wrapper.find('[data-testid="sequence-grafcet-panel"]').exists()).toBe(true)
      // The GRAFCET view shows the chart itself, so the panel steps aside.
      await router.push('/workspace/products/3/sequences/4/grafcet')
      await flushPromises()
      expect(wrapper.find('[data-testid="sequence-grafcet-panel"]').exists()).toBe(false)
      wrapper.unmount()
    } finally {
      vi.stubGlobal('matchMedia', original)
    }
    const { wrapper } = await mountView()
    expect(wrapper.find('[data-testid="sequence-grafcet-panel"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
