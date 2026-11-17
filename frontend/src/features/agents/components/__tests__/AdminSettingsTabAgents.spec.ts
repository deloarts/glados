import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { UserResponse } from '@/core/types/userResponse'
import type { AgentSettings, UpdateAgentSettingsCommand } from '../../types/agentTypes'

const getMock = vi.fn<() => Promise<AgentSettings>>()
const updateMock = vi.fn<(cmd: UpdateAgentSettingsCommand) => Promise<AgentSettings>>()

vi.mock('@/features/agents/api/agentsApi', () => ({
  getAgentSettings: () => getMock(),
  updateAgentSettings: (cmd: UpdateAgentSettingsCommand) => updateMock(cmd),
}))

const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

import AdminSettingsTabAgents from '../AdminSettingsTabAgents.vue'

function makeSettings(overrides: Partial<AgentSettings> = {}): AgentSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    enabled: false,
    token_max_lifetime_days: 30,
    token_idle_revoke_days: 14,
    include_person_names: false,
    include_costs: false,
    allowed_origins: [],
    calls_per_minute: 120,
    drafts_per_hour: 20,
    approved_providers: '',
    ai_policy_url: null,
    processing_approved_at: null,
    ...overrides,
  }
}

const APPROVED = makeSettings({
  enabled: true,
  approved_providers: 'Claude',
  processing_approved_at: '2026-11-01T08:00:00Z',
})

async function mountTab(settings: AgentSettings, permissions = ['read:settings', 'write:settings']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    id: 1,
    is_systemuser: false,
    is_shared_account: false,
    permissions,
  } as unknown as UserResponse
  getMock.mockResolvedValue(settings)
  const wrapper = mountWithApp(AdminSettingsTabAgents, { pinia })
  await flushPromises()
  return wrapper
}

describe('AdminSettingsTabAgents', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps agent access off until the approval names its providers', async () => {
    const wrapper = await mountTab(makeSettings())

    expect(wrapper.find<HTMLInputElement>('#agents-enabled').element.disabled).toBe(true)
    expect(wrapper.find<HTMLInputElement>('#agents-approved').element.disabled).toBe(true)

    await wrapper.find('#agents-providers').setValue('Claude')
    await wrapper.find('#agents-approved').setValue(true)

    expect(wrapper.find<HTMLInputElement>('#agents-enabled').element.disabled).toBe(false)
    wrapper.unmount()
  })

  it('saves the approval, access and origins in one command', async () => {
    updateMock.mockResolvedValue(APPROVED)
    const wrapper = await mountTab(makeSettings())

    await wrapper.find('#agents-providers').setValue(' Claude ')
    await wrapper.find('#agents-approved').setValue(true)
    await wrapper.find('#agents-enabled').setValue(true)
    await wrapper.find('#agents-origins').setValue('https://a.example\nhttps://b.example')
    await wrapper.find('[data-testid="agents-save"]').trigger('click')
    await flushPromises()

    expect(confirmRequireMock).not.toHaveBeenCalled()
    expect(updateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        processing_approved: true,
        approved_providers: 'Claude',
        ai_policy_url: null,
        enabled: true,
        allowed_origins: ['https://a.example', 'https://b.example'],
      }),
    )
    wrapper.unmount()
  })

  it('asks before a change that makes every user consent again', async () => {
    updateMock.mockResolvedValue(APPROVED)
    const wrapper = await mountTab(APPROVED)

    await wrapper.find('#agents-names').setValue(true)
    await wrapper.find('[data-testid="agents-save"]').trigger('click')
    await flushPromises()

    expect(updateMock).not.toHaveBeenCalled()
    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    confirmRequireMock.mock.calls[0]![0].accept?.()
    await flushPromises()

    expect(updateMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_person_names: true, processing_approved: true }),
    )
    wrapper.unmount()
  })

  it('withdrawing the approval switches access off', async () => {
    updateMock.mockResolvedValue(makeSettings({ approved_providers: 'Claude' }))
    const wrapper = await mountTab(APPROVED)

    await wrapper.find('#agents-approved').setValue(false)
    await wrapper.find('[data-testid="agents-save"]').trigger('click')
    await flushPromises()

    expect(updateMock).toHaveBeenCalledWith(
      expect.objectContaining({ processing_approved: false, enabled: false }),
    )
    wrapper.unmount()
  })

  it('disables saving without write:settings', async () => {
    const wrapper = await mountTab(APPROVED, ['read:settings'])

    expect(
      wrapper.find<HTMLButtonElement>('[data-testid="agents-save"]').element.disabled,
    ).toBe(true)
    wrapper.unmount()
  })
})
