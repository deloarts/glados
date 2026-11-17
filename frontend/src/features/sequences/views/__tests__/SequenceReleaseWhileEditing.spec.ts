import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { controlledDocumentFields } from '@/test-utils/controlledDocument'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { SequenceResponse, SequenceUpdateRequest } from '../../types/sequence'

// The confirm dialog's accept is called directly instead of driving the dialog.
const confirmRequire = vi.fn<(options: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({ useConfirm: () => ({ require: confirmRequire }) }))

const sequences = new Map<number, SequenceResponse>()
const calls: string[] = []

vi.mock('../../api/sequencesApi', () => ({
  getSequence: async (id: number) => sequences.get(id),
  getSequenceRevisions: async (id: number) => [sequences.get(id)],
  updateSequence: async (id: number, body: SequenceUpdateRequest) => {
    calls.push('save')
    const saved = { ...sequences.get(id)!, name: body.name, steps: body.steps, step_count: body.steps.length }
    sequences.set(id, saved)
    return saved
  },
  lockSequence: async (id: number) => {
    const locked = { ...sequences.get(id)!, locked_by_id: 1, locked_by_full_name: 'Author', locked_at: '2026-10-23T09:00:00Z', lock_expires_at: '2099-01-01T00:00:00Z' }
    sequences.set(id, locked)
    return locked
  },
  unlockSequence: async (id: number) => sequences.get(id),
  // The release ends the edit lock, as the server does.
  releaseSequence: async (id: number) => {
    calls.push('release')
    const released = { ...sequences.get(id)!, released_at: '2026-10-23T10:00:00Z', locked_by_id: null, locked_by_full_name: null, locked_at: null, lock_expires_at: null }
    sequences.set(id, released)
    return released
  },
  reviseSequence: vi.fn<() => Promise<void>>(),
  markSequenceInvalid: vi.fn<() => Promise<void>>(),
  deleteSequence: vi.fn<() => Promise<void>>(),
}))
vi.mock('../../api/productVariantsApi', () => ({ getProductVariants: async () => [] }))
vi.mock('../../api/productApi', () => ({
  getSequenceProduct: async () => ({ id: 3, archived: false, designated_user_id: 1, contains_pneumatics: true }),
}))
vi.mock('@/features/product-devices/api/productDevicesApi', () => ({ getProductDevices: async () => [] }))
vi.mock('@/features/product-devices/api/productDeviceResourcesApi', () => ({
  getProductDeviceOptions: () => Promise.resolve([]),
  getProductDeviceKinds: () => Promise.resolve([]),
}))

import SequenceDetailView from '../SequenceDetailView.vue'

function sequence(): SequenceResponse {
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
  }
}

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { id: 1, permissions: ['write:sequences', 'release:sequences'], is_systemuser: false } as never
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/workspace/products/:id(\\d+)/sequences/:sequenceId(\\d+)/:view(diagram|grafcet)?',
        name: 'SequenceDetail',
        component: SequenceDetailView,
      },
      { path: '/workspace/products/:id(\\d+)/:tab?', name: 'ProductDetail', component: { template: '<div />' } },
    ],
  })
  await router.push('/workspace/products/3/sequences/4')
  const Host = defineComponent({ render: () => h(RouterView) })
  const wrapper = mountWithApp(Host, { pinia, global: { plugins: [router], directives: { tooltip: Tooltip } } })
  await flushPromises()
  return wrapper
}

describe('SequenceDetailView release while editing', () => {
  beforeEach(() => {
    localStorage.clear()
    calls.length = 0
    confirmRequire.mockReset()
    sequences.clear()
    sequences.set(4, sequence())
  })

  it('reads Done without changes and Discard with them', async () => {
    const wrapper = await mountView()
    await wrapper.find('[data-testid="sequence-edit"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="sequence-finish"]').text()).toBe('Done')

    await wrapper.find('[data-testid="sequence-add-step"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="sequence-finish"]').text()).toBe('Discard')
    wrapper.unmount()
  })

  it('saves the unsaved steps first, releases them and ends editing', async () => {
    const wrapper = await mountView()
    await wrapper.find('[data-testid="sequence-edit"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="sequence-add-step"]').trigger('click')
    await flushPromises()

    const release = wrapper.find('[data-testid="sequence-release"]')
    expect(release.attributes('disabled')).toBeUndefined()
    await release.trigger('click')
    const options = confirmRequire.mock.calls[0]![0]
    expect(options.message).toContain('Your unsaved changes are saved first.')
    await (options.accept as () => Promise<void>)()
    await flushPromises()

    expect(calls).toEqual(['save', 'release'])
    expect(sequences.get(4)!.steps).toHaveLength(1)
    expect(wrapper.find('[data-testid="sequence-save"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sequence-release"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
