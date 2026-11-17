import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import type { UserResponse } from '@/core/types/userResponse'
import type { CreatedToken, CreateTokenCommand } from '@/shared/types/tokenTypes'

const createMock = vi.fn<(cmd: CreateTokenCommand) => Promise<CreatedToken>>()

vi.mock('@/shared/api/createTokenApi', () => ({
  createTokenApi: () => ({ create: (cmd: CreateTokenCommand) => createMock(cmd) }),
}))

import AgentTokenDialog from '../AgentTokenDialog.vue'

async function mountDialog(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    id: 1,
    is_systemuser: false,
    is_shared_account: false,
    permissions,
  } as unknown as UserResponse
  const host = useHostStore()
  host.agentReadScopes = ['use:mcp']
  host.agentDraftScopes = ['use:mcp', 'write:orders', 'write:lots']
  host.agentTokenMaxLifetimeDays = 14
  const wrapper = mountWithApp(AgentTokenDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function find<T extends Element>(selector: string): T {
  return document.body.querySelector<T>(selector)!
}

describe('AgentTokenDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('grants only the draft scopes the user holds, within the agent lifetime', async () => {
    createMock.mockResolvedValue({ secret: 'glados_pat_secret' } as CreatedToken)
    const wrapper = await mountDialog(['use:mcp', 'write:pat', 'write:orders'])

    find<HTMLInputElement>('#agent-preset-draft').click()
    await flushPromises()
    expect(document.body.textContent).toContain('Write Production Lots')
    expect(find<HTMLButtonElement>('[data-testid="agent-token-create"]').disabled).toBe(true)

    const password = find<HTMLInputElement>('#agent-token-password')
    password.value = 'my-password'
    password.dispatchEvent(new Event('input'))
    await flushPromises()
    find<HTMLButtonElement>('[data-testid="agent-token-create"]').click()
    await flushPromises()

    expect(createMock).toHaveBeenCalledWith({
      name: expect.stringMatching(/^Agent /),
      permissions: ['use:mcp', 'write:orders'],
      expires_in_days: 14,
      password: 'my-password',
    })
    expect(find<HTMLInputElement>('[data-testid="agent-token-secret"]').value).toBe(
      'glados_pat_secret',
    )
    const command = find('[data-testid="agent-token-command"]').textContent ?? ''
    expect(command).toContain('claude mcp add --transport http glados')
    expect(command).toContain('/api/v1/mcp')
    expect(command).toContain('Bearer glados_pat_secret')
    wrapper.unmount()
  })

  it('cannot create a token without use:mcp', async () => {
    const wrapper = await mountDialog(['write:pat'])

    expect(find<HTMLButtonElement>('[data-testid="agent-token-create"]').disabled).toBe(true)
    wrapper.unmount()
  })
})
