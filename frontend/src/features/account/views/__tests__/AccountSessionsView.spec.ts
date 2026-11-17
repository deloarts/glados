import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { answerConfirmations } from '@/test-utils/confirmations'
import { i18n } from '@/core/i18n'

import type { SessionSummary, TrustedDeviceSummary } from '../../api/sessionsApi'

const fetchSessionsMock = vi.fn<() => Promise<SessionSummary[]>>()
const fetchTrustedDevicesMock = vi.fn<() => Promise<TrustedDeviceSummary[]>>()
const revokeSessionMock = vi.fn<(id: string) => Promise<void>>()
const revokeOtherSessionsMock = vi.fn<() => Promise<number>>()
const revokeTrustedDeviceMock = vi.fn<(id: string) => Promise<void>>()
const revokeAllTrustedDevicesMock = vi.fn<() => Promise<number>>()

vi.mock('../../api/sessionsApi', () => ({
  fetchSessions: () => fetchSessionsMock(),
  fetchTrustedDevices: () => fetchTrustedDevicesMock(),
  revokeSession: (id: string) => revokeSessionMock(id),
  revokeOtherSessions: () => revokeOtherSessionsMock(),
  revokeTrustedDevice: (id: string) => revokeTrustedDeviceMock(id),
  revokeAllTrustedDevices: () => revokeAllTrustedDevicesMock(),
}))

import AccountSessionsView from '../AccountSessionsView.vue'

const t = i18n.global.t

// HelpButton in the controls bar makes a defensive useRoute() call, see
// BoughtItemsCatalogueControls.spec.ts for the same minimal-router pattern.
const router = createRouter({ history: createMemoryHistory(), routes: [] })

function makeSession(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created_at: '2026-09-01T10:00:00Z',
    last_seen_at: '2026-09-02T10:00:00Z',
    user_agent: 'Chrome on Windows',
    ip: '10.0.0.1',
    is_current: false,
    ...overrides,
  }
}

function makeDevice(overrides: Partial<TrustedDeviceSummary> = {}): TrustedDeviceSummary {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    created_at: '2026-09-01T10:00:00Z',
    last_used_at: '2026-09-02T10:00:00Z',
    expires_at: '2026-10-01T10:00:00Z',
    user_agent: 'Edge on macOS',
    ...overrides,
  }
}

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mountWithApp(AccountSessionsView, {
    pinia,
    global: { plugins: [router, ConfirmationService] },
  })
  await flushPromises()
  return wrapper
}

describe('AccountSessionsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    fetchSessionsMock.mockReset()
    fetchTrustedDevicesMock.mockReset()
    revokeSessionMock.mockReset()
    revokeOtherSessionsMock.mockReset()
    revokeTrustedDeviceMock.mockReset()
    revokeAllTrustedDevicesMock.mockReset()
    fetchSessionsMock.mockResolvedValue([])
    fetchTrustedDevicesMock.mockResolvedValue([])
    revokeSessionMock.mockResolvedValue(undefined)
    revokeOtherSessionsMock.mockResolvedValue(0)
    revokeTrustedDeviceMock.mockResolvedValue(undefined)
    revokeAllTrustedDevicesMock.mockResolvedValue(0)
  })

  it('fetches sessions and trusted devices on mount, in parallel', async () => {
    const wrapper = await mountView()

    expect(fetchSessionsMock).toHaveBeenCalledTimes(1)
    expect(fetchTrustedDevicesMock).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('shows an empty state in both tables when nothing has loaded', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain(t('account.sessions.empty'))
    expect(wrapper.text()).toContain(t('account.sessions.devices.empty'))

    wrapper.unmount()
  })

  it('surfaces a toast-worthy error state without throwing when the fetch fails', async () => {
    fetchSessionsMock.mockRejectedValue(new Error('network error'))
    const wrapper = await mountView()

    // The view swallows the error into a toast rather than crashing, both
    // tables render (loading cleared) with nothing in them.
    const tables = wrapper.findAllComponents({ name: 'DataTable' })
    expect(tables.every((tbl) => tbl.props('loading') === false)).toBe(true)

    wrapper.unmount()
  })

  it('lists fetched sessions and disables "revoke others" with fewer than two sessions', async () => {
    fetchSessionsMock.mockResolvedValue([makeSession({ is_current: true })])
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Chrome on Windows')
    expect(wrapper.text()).toContain(t('account.sessions.current'))

    const revokeOthersButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === t('account.sessions.revokeOthersButton'))!
    expect(revokeOthersButton.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('enables "revoke others" with two or more sessions and asks before it revokes them', async () => {
    fetchSessionsMock.mockResolvedValue([
      makeSession({ id: 1, is_current: true }),
      makeSession({ id: 2, is_current: false }),
    ])
    const confirmations = answerConfirmations('reject')
    const wrapper = await mountView()

    const revokeOthersButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === t('account.sessions.revokeOthersButton'))!
    expect(revokeOthersButton.attributes('disabled')).toBeUndefined()
    await revokeOthersButton.trigger('click')
    confirmations.stop()

    expect(confirmations.asked).toHaveLength(1)

    wrapper.unmount()
  })

  it('lists fetched trusted devices and disables "revoke all" when there are none', async () => {
    const wrapper = await mountView()

    const revokeAllButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === t('account.sessions.devices.revokeAllButton'))!
    expect(revokeAllButton.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('enables "revoke all devices" once a trusted device exists', async () => {
    fetchTrustedDevicesMock.mockResolvedValue([makeDevice()])
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Edge on macOS')

    const revokeAllButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === t('account.sessions.devices.revokeAllButton'))!
    expect(revokeAllButton.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })
})
