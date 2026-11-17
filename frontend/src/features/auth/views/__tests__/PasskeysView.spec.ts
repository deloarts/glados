import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { answerConfirmations } from '@/test-utils/confirmations'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { UserResponse } from '@/core/types/userResponse'

import type { PasskeySummary } from '../../api/passkeys'

const fetchMyPasskeysMock = vi.fn<() => Promise<PasskeySummary[]>>()
const setUpMock =
  vi.fn<(password: string, name: string, user: unknown) => Promise<PasskeySummary>>()
const supportedMock = vi.fn<() => boolean>()
const deleteAllMock = vi.fn<() => Promise<number>>()
const renameMock = vi.fn<(publicId: string, name: string) => Promise<PasskeySummary>>()

vi.mock('../../api/passkeys', () => ({
  fetchMyPasskeys: () => fetchMyPasskeysMock(),
  deleteMyPasskey: vi.fn<() => Promise<void>>(),
  deleteAllMyPasskeys: () => deleteAllMock(),
  renameMyPasskey: (publicId: string, name: string) => renameMock(publicId, name),
}))

vi.mock('../../utils/passkeySetup', () => ({
  setUpPasskeyOnThisDevice: (password: string, name: string, user: unknown) =>
    setUpMock(password, name, user),
}))

vi.mock('../../utils/webauthn', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../utils/webauthn')>()),
  passkeysSupported: () => supportedMock(),
}))

import PasskeysView from '../PasskeysView.vue'

const t = i18n.global.t

const router = createRouter({ history: createMemoryHistory(), routes: [] })

function makePasskey(overrides: Partial<PasskeySummary> = {}): PasskeySummary {
  return {
    id: 1,
    public_id: '33333333-3333-3333-3333-333333333333',
    name: 'Office PC',
    created_at: '2026-10-01T10:00:00Z',
    last_used_at: null,
    backed_up: false,
    ...overrides,
  }
}

async function mountView(user: Partial<UserResponse> = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    id: 7,
    username: 'alice',
    full_name: 'Alice Smith',
    is_systemuser: false,
    ...user,
  } as UserResponse

  const wrapper = mountWithApp(PasskeysView, {
    pinia,
    global: { plugins: [router, ConfirmationService] },
  })
  await flushPromises()
  return wrapper
}

function addButton(wrapper: Awaited<ReturnType<typeof mountView>>) {
  return wrapper.find('[data-testid="passkeys-add"]')
}

describe('PasskeysView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    fetchMyPasskeysMock.mockResolvedValue([])
    supportedMock.mockReturnValue(true)
  })

  it('lists the passkeys', async () => {
    fetchMyPasskeysMock.mockResolvedValue([makePasskey({ backed_up: true })])
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Office PC')
    expect(wrapper.text()).toContain(t('account.passkeys.synced') as string)
    wrapper.unmount()
  })

  it('shows the empty state without passkeys', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain(t('account.passkeys.empty') as string)
    wrapper.unmount()
  })

  it('disables adding where the browser cannot use passkeys', async () => {
    supportedMock.mockReturnValue(false)
    const wrapper = await mountView()

    expect(addButton(wrapper).attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('disables adding for the system user', async () => {
    const wrapper = await mountView({ is_systemuser: true })

    expect(addButton(wrapper).attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('disables Remove All Passkeys without passkeys', async () => {
    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="passkeys-remove-all"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('removes all passkeys after confirming', async () => {
    fetchMyPasskeysMock.mockResolvedValue([makePasskey()])
    deleteAllMock.mockResolvedValue(1)
    const confirmations = answerConfirmations('accept')
    const wrapper = await mountView()

    await wrapper.find('[data-testid="passkeys-remove-all"]').trigger('click')
    await flushPromises()
    confirmations.stop()

    expect(deleteAllMock).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('renames a passkey', async () => {
    const passkey = makePasskey()
    fetchMyPasskeysMock.mockResolvedValue([passkey])
    renameMock.mockResolvedValue(makePasskey({ name: 'Laptop' }))
    const wrapper = await mountView()

    await wrapper.find('[data-testid="passkeys-rename"]').trigger('click')
    await flushPromises()
    const input = wrapper
      .findAllComponents({ name: 'InputText' })
      .find((c) => c.attributes('id') === 'passkey-rename-name')!
    await input.vm.$emit('update:modelValue', ' Laptop ')
    document
      .querySelector<HTMLFormElement>('#passkey-rename-form')!
      .dispatchEvent(new Event('submit'))
    await flushPromises()

    expect(renameMock).toHaveBeenCalledWith(passkey.public_id, 'Laptop')
    expect(fetchMyPasskeysMock).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('adds a passkey with the confirmed password', async () => {
    setUpMock.mockResolvedValue(makePasskey())
    const wrapper = await mountView()

    await addButton(wrapper).trigger('click')
    await flushPromises()
    // The dialog is teleported; findComponent still reaches into it.
    await wrapper.findComponent({ name: 'Password' }).vm.$emit('update:modelValue', 'secret')
    document.querySelector<HTMLFormElement>('#passkey-add-form')!.dispatchEvent(new Event('submit'))
    await flushPromises()

    expect(setUpMock).toHaveBeenCalledWith('secret', expect.any(String), expect.anything())
    expect(fetchMyPasskeysMock).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
})
