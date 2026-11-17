import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { AgentCreatedRecord } from '../../types/agentTypes'

const findMock = vi.fn<(refs: string[]) => Promise<AgentCreatedRecord[]>>()

vi.mock('@/features/agents/api/agentsApi', () => ({
  findAgentCreatedRecords: (refs: string[]) => findMock(refs),
}))

import AgentBadge from '../AgentBadge.vue'

const DRAFTED = '11111111-1111-1111-1111-111111111111'
const MANUAL = '22222222-2222-2222-2222-222222222222'

const List = defineComponent({
  setup() {
    return () =>
      h('div', [
        h(AgentBadge, { kind: 'order', publicId: DRAFTED }),
        h(AgentBadge, { kind: 'order', publicId: MANUAL }),
      ])
  },
})

describe('AgentBadge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('asks once for every row of a render and marks only the agent drafts', async () => {
    findMock.mockResolvedValue([
      {
        ref: `order:${DRAFTED}`,
        token_name: 'Agent 2026-11-06',
        token_kind: 'pat',
        user_id: 1,
        called_at: '2026-11-06T08:00:00Z',
      },
    ])
    const wrapper = mountWithApp(List)
    await flushPromises()

    expect(findMock).toHaveBeenCalledTimes(1)
    expect(findMock).toHaveBeenCalledWith([`order:${DRAFTED}`, `order:${MANUAL}`])
    expect(wrapper.findAll('[data-testid="agent-badge"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('shows nothing when the lookup fails', async () => {
    findMock.mockRejectedValue(new Error('offline'))
    const wrapper = mountWithApp(List)
    await flushPromises()

    expect(wrapper.find('[data-testid="agent-badge"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
