import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'
import type { UserResponse } from '@/core/types/userResponse'
import type { PageResponse } from '@/core/api/types'
import type { AgentCall, AgentConsentStatus } from '../../types/agentTypes'

const statusMock = vi.fn<() => Promise<AgentConsentStatus>>()
const giveMock = vi.fn<(version: number) => Promise<AgentConsentStatus>>()
const withdrawMock = vi.fn<() => Promise<AgentConsentStatus>>()
const callsMock = vi.fn<() => Promise<PageResponse<AgentCall>>>()

vi.mock('@/features/agents/api/agentsApi', () => ({
  getMyAgentConsent: () => statusMock(),
  giveAgentConsent: (version: number) => giveMock(version),
  withdrawAgentConsent: () => withdrawMock(),
  getAgentCalls: () => callsMock(),
}))

const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

import AccountAgentsView from '../AccountAgentsView.vue'

const t = i18n.global.t

function makeStatus(overrides: Partial<AgentConsentStatus> = {}): AgentConsentStatus {
  return {
    access_ready: true,
    may_use_agents: true,
    approved_providers: 'Claude',
    ai_policy_url: null,
    include_person_names: false,
    include_costs: false,
    consent_version: 1,
    consented_at: null,
    consent_current: false,
    ...overrides,
  }
}

async function mountView(status: AgentConsentStatus, permissions = ['use:mcp', 'write:pat']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    id: 1,
    is_systemuser: false,
    is_shared_account: false,
    permissions,
  } as unknown as UserResponse
  useHostStore().agentReadScopes = ['use:mcp']
  useHostStore().agentDraftScopes = ['use:mcp', 'write:orders', 'write:lots']
  statusMock.mockResolvedValue(status)
  callsMock.mockResolvedValue({ items: [], total: 0, limit: 25, skip: 0 })
  const wrapper = mountWithApp(AccountAgentsView, { pinia, attachTo: document.body })
  await flushPromises()
  return wrapper
}

function bodyButton(testId: string): HTMLButtonElement | null {
  return document.body.querySelector<HTMLButtonElement>(`[data-testid="${testId}"]`)
}

describe('AccountAgentsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('asks for the consent before the first agent token and then opens the token dialog', async () => {
    giveMock.mockResolvedValue(
      makeStatus({ consented_at: '2026-11-06T08:00:00Z', consent_current: true }),
    )
    const wrapper = await mountView(makeStatus())

    expect(wrapper.find('[data-testid="agent-consent-state"]').text()).toBe(
      t('agents.account.consentMissing'),
    )
    await wrapper.find('[data-testid="agent-new-token"]').trigger('click')
    await flushPromises()

    expect(bodyButton('agent-consent-confirm')).not.toBeNull()
    document.body.querySelector<HTMLInputElement>('[data-testid="agent-consent-agree"]')!.click()
    await flushPromises()
    bodyButton('agent-consent-confirm')!.click()
    await flushPromises()

    expect(giveMock).toHaveBeenCalledWith(1)
    expect(document.body.querySelector('[data-testid="agent-token-dialog"]')).not.toBeNull()
    expect(wrapper.find('[data-testid="agent-consent-state"]').text()).toBe(
      t('agents.account.consentGiven'),
    )
    wrapper.unmount()
  })

  it('goes straight to the token dialog with a current consent', async () => {
    const wrapper = await mountView(
      makeStatus({ consented_at: '2026-11-06T08:00:00Z', consent_current: true }),
    )

    expect(wrapper.find('[data-testid="agent-give-consent"]').exists()).toBe(false)
    await wrapper.find('[data-testid="agent-new-token"]').trigger('click')
    await flushPromises()

    expect(document.body.querySelector('[data-testid="agent-consent-dialog"]')).toBeNull()
    expect(document.body.querySelector('[data-testid="agent-token-dialog"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('shows the actions disabled without use:mcp', async () => {
    const wrapper = await mountView(makeStatus({ may_use_agents: false }), ['write:pat'])

    expect(
      wrapper.find<HTMLButtonElement>('[data-testid="agent-new-token"]').element.disabled,
    ).toBe(true)
    expect(
      wrapper.find<HTMLButtonElement>('[data-testid="agent-give-consent"]').element.disabled,
    ).toBe(true)
    wrapper.unmount()
  })

  it('shows New Agent Token disabled without write:pat and names the permission, while consent stays open', async () => {
    const wrapper = await mountView(makeStatus(), ['use:mcp'])

    const newToken = wrapper.find<HTMLButtonElement>('[data-testid="agent-new-token"]')
    expect(newToken.element.disabled).toBe(true)
    expect(
      (newToken.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)
        ?.$_ptooltipValue,
    ).toBe('This needs the permission Write Access Token.')
    expect(
      wrapper.find<HTMLButtonElement>('[data-testid="agent-give-consent"]').element.disabled,
    ).toBe(false)
    wrapper.unmount()
  })

  it('withdraws after confirming, also while agent access is off', async () => {
    withdrawMock.mockResolvedValue(makeStatus({ access_ready: false }))
    const wrapper = await mountView(
      makeStatus({ access_ready: false, consented_at: '2026-11-01T08:00:00Z' }),
    )

    expect(wrapper.text()).toContain(t('agents.account.accessOff'))
    expect(wrapper.find('[data-testid="agent-new-token"]').exists()).toBe(false)
    await wrapper.find('[data-testid="agent-withdraw-consent"]').trigger('click')
    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    confirmRequireMock.mock.calls[0]![0].accept?.()
    await flushPromises()

    expect(withdrawMock).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="agent-withdraw-consent"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
