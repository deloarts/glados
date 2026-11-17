import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive, ref } from 'vue'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { LiveResource } from '@/core/realtime/resources'
import type { LiveSignal } from '@/core/realtime/types'
import type { Acknowledgement, AcknowledgementRecipient } from '../../types/acknowledgementTypes'

// Same technique as AdminSettingsTabUsers.spec.ts: replace the composable so
// `accept` can be invoked directly instead of driving a real
// <ConfirmDialog/>'s DOM.
const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

// Same fake liveStore technique as useAutoPlanRunLiveSync.spec.ts /
// AnnouncementsHandler.spec.ts, for full control over when a signal "arrives".
const subscribers = new Map<string, (signal: LiveSignal) => void>()
const fakeLiveStore = reactive({
  reconnectCount: ref(0),
  on: (resource: string, handler: (signal: LiveSignal) => void) => {
    subscribers.set(resource, handler)
    return () => subscribers.delete(resource)
  },
})
vi.mock('@/core/realtime/liveStore', () => ({ useLiveStore: () => fakeLiveStore }))

function fireSignal(): void {
  subscribers.get(LiveResource.ANNOUNCEMENTS)?.({
    resource: LiveResource.ANNOUNCEMENTS,
    id: 1,
    action: 'updated',
    actor_id: null,
  })
}

const getAcknowledgementsMock = vi.fn<() => Promise<Acknowledgement[]>>()
const setAcknowledgementEnabledMock =
  vi.fn<(publicId: string, enabled: boolean) => Promise<Acknowledgement>>()
const deleteAcknowledgementMock = vi.fn<(publicId: string) => Promise<void>>()
const getAcknowledgementRecipientsMock =
  vi.fn<(publicId: string) => Promise<AcknowledgementRecipient[]>>()

vi.mock('../../api/getAcknowledgements', () => ({
  getAcknowledgements: () => getAcknowledgementsMock(),
}))
vi.mock('../../api/setAcknowledgementEnabled', () => ({
  setAcknowledgementEnabled: (id: string, enabled: boolean) =>
    setAcknowledgementEnabledMock(id, enabled),
}))
vi.mock('../../api/deleteAcknowledgement', () => ({
  deleteAcknowledgement: (id: string) => deleteAcknowledgementMock(id),
}))
vi.mock('../../api/getAcknowledgementRecipients', () => ({
  getAcknowledgementRecipients: (id: string) => getAcknowledgementRecipientsMock(id),
}))

import AcknowledgementsPanel from '../AcknowledgementsPanel.vue'

function makeAck(overrides: Partial<Acknowledgement> = {}): Acknowledgement {
  return {
    id: 1,
    public_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    text: 'Read the new safety policy.',
    severity: 'warning',
    enabled: true,
    show_when: 'immediately',
    created_at: '2026-01-01T00:00:00Z',
    created_by_username: 'admin',
    recipients_total: 3,
    recipients_acknowledged: 1,
    ...overrides,
  }
}

function mountPanel(canWrite = true) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(AcknowledgementsPanel, {
    pinia,
    attachTo: document.body,
    props: { canWrite },
  })
  return wrapper
}

describe('AcknowledgementsPanel', () => {
  beforeEach(() => {
    getAcknowledgementsMock.mockReset()
    setAcknowledgementEnabledMock.mockReset()
    deleteAcknowledgementMock.mockReset()
    getAcknowledgementRecipientsMock.mockReset()
    getAcknowledgementRecipientsMock.mockResolvedValue([])
    confirmRequireMock.mockReset()
    subscribers.clear()
    document.body.innerHTML = ''
  })

  it('loads and renders acknowledgements on mount', async () => {
    getAcknowledgementsMock.mockResolvedValue([makeAck()])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('Read the new safety policy.')
    expect(wrapper.text()).toContain('1 / 3')

    wrapper.unmount()
  })

  it('refetches the list on the live "announcements" signal', async () => {
    getAcknowledgementsMock.mockResolvedValue([])
    const wrapper = mountPanel()
    await flushPromises()
    expect(getAcknowledgementsMock).toHaveBeenCalledTimes(1)

    fireSignal()
    await flushPromises()

    expect(getAcknowledgementsMock).toHaveBeenCalledTimes(2)

    wrapper.unmount()
  })

  it('PATCHes enabled when the row toggle is flipped', async () => {
    getAcknowledgementsMock.mockResolvedValue([makeAck({ enabled: true })])
    setAcknowledgementEnabledMock.mockResolvedValue(makeAck({ enabled: false }))
    const wrapper = mountPanel()
    await flushPromises()

    const toggle = wrapper.findComponent({ name: 'ToggleSwitch' })
    await toggle.vm.$emit('update:modelValue', false)
    await flushPromises()

    expect(setAcknowledgementEnabledMock).toHaveBeenCalledWith(
      'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      false,
    )

    wrapper.unmount()
  })

  it('opens the recipients dialog for a row', async () => {
    getAcknowledgementsMock.mockResolvedValue([makeAck()])
    getAcknowledgementRecipientsMock.mockResolvedValue([
      { user_id: 1, username: 'alice', full_name: 'Alice', acknowledged_at: null },
    ])
    const wrapper = mountPanel()
    await flushPromises()

    const recipientsButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-account-multiple-outline')
    expect(recipientsButton).toBeDefined()

    await recipientsButton!.trigger('click')
    await flushPromises()

    expect(getAcknowledgementRecipientsMock).toHaveBeenCalledWith(
      'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    )
    // Dialog teleports to document.body by default (OpenVue's appendTo),
    // so its content lives outside wrapper.element's own subtree, the same
    // reasoning as SystemUserWarningDialog.spec.ts querying document.body
    // directly rather than the wrapper.
    expect(document.body.textContent).toContain('Alice')

    wrapper.unmount()
  })

  it('asks for confirmation, then deletes and reloads on accept', async () => {
    getAcknowledgementsMock.mockResolvedValue([makeAck()])
    deleteAcknowledgementMock.mockResolvedValue(undefined)
    const wrapper = mountPanel()
    await flushPromises()

    const deleteButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-delete-outline')
    await deleteButton!.trigger('click')

    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    expect(deleteAcknowledgementMock).not.toHaveBeenCalled()

    const options = confirmRequireMock.mock.calls[0]![0] as { accept: () => Promise<void> }
    await options.accept()
    await flushPromises()

    expect(deleteAcknowledgementMock).toHaveBeenCalledWith(
      'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    )
    expect(getAcknowledgementsMock).toHaveBeenCalledTimes(2)

    wrapper.unmount()
  })
})
