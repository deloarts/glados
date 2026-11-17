import { afterEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive, ref } from 'vue'

import type { PageResponse } from '@/core/api/types'
import { LiveResource } from '@/core/realtime/resources'
import type { LiveSignal } from '@/core/realtime/types'
import { Permission } from '@/core/auth/permissions'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { mountWithApp } from '@/test-utils/mountWithApp'
import type { SequenceCreateRequest, SequenceResponse, SequenceSummaryResponse } from '../../types/sequence'

const pushMock = vi.fn<(to: unknown) => Promise<void>>()
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: pushMock, resolve: () => ({ href: '/' }) }),
}))

const subscribers = new Map<string, (signal: LiveSignal) => void>()
const fakeLiveStore = reactive({
  reconnectCount: ref(0),
  on: (resource: string, handler: (signal: LiveSignal) => void) => {
    subscribers.set(resource, handler)
    return () => subscribers.delete(resource)
  },
})
vi.mock('@/core/realtime/liveStore', () => ({ useLiveStore: () => fakeLiveStore }))
vi.mock('openvue/useconfirm', () => ({ useConfirm: () => ({ require: vi.fn<() => void>() }) }))

const getSequencesMock = vi.fn<(params: unknown) => Promise<PageResponse<SequenceSummaryResponse>>>()
const createSequenceMock = vi.fn<(body: SequenceCreateRequest) => Promise<SequenceResponse>>()
const getSequenceMock = vi.fn<(id: number) => Promise<SequenceResponse>>()
vi.mock('../../api/sequencesApi', () => ({
  getSequences: (params: unknown) => getSequencesMock(params),
  getSequence: (id: number) => getSequenceMock(id),
  createSequence: (body: SequenceCreateRequest) => createSequenceMock(body),
  deleteSequence: vi.fn<() => Promise<void>>(),
}))

vi.mock('@/features/product-devices/api/productDeviceResourcesApi', () => ({
  getProductDeviceOptions: () => Promise.resolve([]),
  getProductDeviceKinds: () => Promise.resolve([]),
}))

import SequencesTab from '../SequencesTab.vue'
import { useSequencesViewStore } from '../../stores/sequencesViewStore'

function summary(id: number, name: string, overrides: Partial<SequenceSummaryResponse> = {}): SequenceSummaryResponse {
  return {
    id,
    public_id: `s${id}`,
    created: '2026-10-23T08:00:00Z',
    changed: '2026-10-23T09:00:00Z',
    changed_by_id: 1,
    changed_by_full_name: 'Ada',
    creator_id: 1,
    creator_full_name: 'Ada',
    document_number: `SEQ-26-000${id}`,
    lineage: `l${id}`,
    revision: 'A',
    revision_reason: null,
    is_latest: true,
    superseded_at: null,
    read_only: false,
    released_at: null,
    released_by_id: null,
    released_by_full_name: null,
    invalid_at: null,
    invalid_by_id: null,
    invalid_by_full_name: null,
    invalid_reason: null,
    locked_by_id: null,
    locked_by_full_name: null,
    locked_at: null,
    lock_expires_at: null,
    product_id: 3,
    product_number: 'M26001',
    name,
    step_count: 2,
    ...overrides,
  }
}

function page(items: SequenceSummaryResponse[]): PageResponse<SequenceSummaryResponse> {
  return { items, total: items.length, limit: 200, skip: 0 }
}

async function mountTab(permissions?: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  if (permissions) useCurrentUserStore().user = userWithPermissions(permissions)
  const wrapper = mountWithApp(SequencesTab, {
    pinia,
    attachTo: document.body,
    props: { productId: 3, canEditVariants: true },
    global: { stubs: { ProductVariantsDialog: true, ConfirmDialog: true } },
  })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  getSequencesMock.mockReset()
  createSequenceMock.mockReset()
  getSequenceMock.mockReset()
  pushMock.mockReset()
  subscribers.clear()
  document.body.innerHTML = ''
  vi.useRealTimers()
})

describe('SequencesTab', () => {
  it("lists the product's sequences and opens one on click", async () => {
    getSequencesMock.mockResolvedValue(
      page([summary(1, 'Automatic'), summary(2, 'Homing', { released_at: '2026-10-23T10:00:00Z' })]),
    )
    const wrapper = await mountTab()
    expect(getSequencesMock).toHaveBeenCalledWith(expect.objectContaining({ product_id: 3 }))
    expect(wrapper.text()).toContain('SEQ-26-0001')
    expect(wrapper.text()).toContain('Automatic')
    expect(wrapper.text()).toContain('Released')

    await wrapper.findAll('tbody tr')[1]!.trigger('click')
    expect(pushMock).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'SequenceDetail', params: { id: 3, sequenceId: 2 } }),
    )
    wrapper.unmount()
  })

  it('creates a sequence from the controls bar and opens it for editing', async () => {
    getSequencesMock.mockResolvedValue(page([]))
    createSequenceMock.mockResolvedValue({ ...summary(7, 'Manual mode'), steps: [], frozen: null, changes: [] })
    const wrapper = await mountTab()

    useSequencesViewStore().requestCreate()
    await flushPromises()
    await new DOMWrapper(document.body.querySelector('#sequence-create-name')!).setValue('  Manual mode ')
    await new DOMWrapper(document.body.querySelector('[data-testid="sequence-create-submit"]')!).trigger('click')
    await flushPromises()

    expect(createSequenceMock).toHaveBeenCalledWith({ product_id: 3, name: 'Manual mode', steps: [] })
    expect(pushMock).toHaveBeenCalledWith(
      expect.objectContaining({ params: { id: 3, sequenceId: 7 }, query: { action: 'edit' } }),
    )
    wrapper.unmount()
  })

  it('refetches quietly when a sequence changes elsewhere', async () => {
    getSequencesMock.mockResolvedValue(page([]))
    const wrapper = await mountTab()
    vi.useFakeTimers()
    getSequencesMock.mockResolvedValue(page([summary(1, 'Automatic')]))
    subscribers.get(LiveResource.SEQUENCES)!({
      resource: LiveResource.SEQUENCES,
      id: 1,
      action: 'updated',
      actor_id: null,
    })
    await vi.advanceTimersByTimeAsync(400)
    await flushPromises()
    expect(wrapper.text()).toContain('Automatic')
    wrapper.unmount()
  })

  it('copies a sequence from its context menu into a new draft and opens it for editing', async () => {
    const steps = [{ key: 's1', description: 'Clamp', transitions: [{ key: 't1', target: 'end' }] }]
    getSequencesMock.mockResolvedValue(page([summary(2, 'Homing', { released_at: '2026-10-23T10:00:00Z' })]))
    getSequenceMock.mockResolvedValue({ ...summary(2, 'Homing'), steps, frozen: null, changes: [] })
    createSequenceMock.mockResolvedValue({ ...summary(8, 'Homing (copy)'), steps, frozen: null, changes: [] })
    const wrapper = await mountTab()

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()
    const copy = [...document.body.querySelectorAll('[role="menuitem"]')].find((item) => item.textContent?.trim() === 'Copy')
    await new DOMWrapper(copy!.querySelector('a, div')!).trigger('click')
    await flushPromises()
    const name = document.body.querySelector<HTMLInputElement>('#sequence-create-name')!
    expect(name.value).toBe('Homing (copy)')
    await new DOMWrapper(document.body.querySelector('[data-testid="sequence-create-submit"]')!).trigger('click')
    await flushPromises()

    expect(getSequenceMock).toHaveBeenCalledWith(2)
    expect(createSequenceMock).toHaveBeenCalledWith({ product_id: 3, name: 'Homing (copy)', steps })
    expect(pushMock).toHaveBeenCalledWith(
      expect.objectContaining({ params: { id: 3, sequenceId: 8 }, query: { action: 'edit' } }),
    )
    wrapper.unmount()
  })

  it('shows Copy disabled with the missing permission as its title without Write Flow Sequences', async () => {
    getSequencesMock.mockResolvedValue(page([summary(2, 'Homing')]))
    const wrapper = await mountTab([])

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()
    const copy = [...document.body.querySelectorAll('[role="menuitem"]')].find((item) => item.textContent?.trim() === 'Copy')
    expect(copy?.getAttribute('aria-disabled')).toBe('true')
    const t = i18n.global.t
    expect(copy?.querySelector('a')?.getAttribute('title')).toBe(
      t('common.permissionMissing', { permission: t('settings.users.permissions.writeSequences') }),
    )
    wrapper.unmount()
  })

  it('offers Copy without a title to a user with Write Flow Sequences', async () => {
    getSequencesMock.mockResolvedValue(page([summary(2, 'Homing')]))
    const wrapper = await mountTab([Permission.WRITE_SEQUENCES])

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()
    const copy = [...document.body.querySelectorAll('[role="menuitem"]')].find((item) => item.textContent?.trim() === 'Copy')
    expect(copy?.getAttribute('aria-disabled')).not.toBe('true')
    expect(copy?.querySelector('a')?.hasAttribute('title')).toBe(false)
    wrapper.unmount()
  })

  it('names the missing permission on a draft step and gives a step its state rules out no reason', async () => {
    getSequencesMock.mockResolvedValue(page([summary(2, 'Homing')]))
    const wrapper = await mountTab([Permission.WRITE_SEQUENCES])

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()
    const entry = (label: string) =>
      [...document.body.querySelectorAll('[role="menuitem"]')].find((item) => item.textContent?.trim() === label)
    const t = i18n.global.t
    const release = entry(t('documents.menu.release'))
    expect(release?.getAttribute('aria-disabled')).toBe('true')
    expect(release?.querySelector('a')?.getAttribute('title')).toBe(
      t('common.permissionMissing', { permission: t('settings.users.permissions.releaseSequences') }),
    )
    const invalidate = entry(t('documents.menu.invalidate'))
    expect(invalidate?.getAttribute('aria-disabled')).toBe('true')
    expect(invalidate?.querySelector('a')?.hasAttribute('title')).toBe(false)
    wrapper.unmount()
  })
})
