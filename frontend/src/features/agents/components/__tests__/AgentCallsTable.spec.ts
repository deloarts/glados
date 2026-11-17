import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import type { PageResponse } from '@/core/api/types'
import type { AgentCall } from '../../types/agentTypes'

const callsMock = vi.fn<() => Promise<PageResponse<AgentCall>>>()

vi.mock('@/features/agents/api/agentsApi', () => ({
  getAgentCalls: () => callsMock(),
}))

import AgentCallsTable from '../AgentCallsTable.vue'

const t = i18n.global.t
const ORDER_ID = '22222222-2222-2222-2222-222222222222'

function makeCall(overrides: Partial<AgentCall> = {}): AgentCall {
  return {
    public_id: '33333333-3333-3333-3333-333333333333',
    called_at: '2026-11-06T08:00:00Z',
    user_id: 1,
    token_kind: 'pat',
    token_name: 'Agent 2026-11-06',
    tool: 'draft_purchase_order',
    arguments: { supplier_id: 4 },
    outcome: 'ok',
    duration_ms: 42,
    error: null,
    created_refs: [`order:${ORDER_ID}`, 'order_item:44444444-4444-4444-4444-444444444444'],
    ...overrides,
  }
}

describe('AgentCallsTable', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('links the drafts a call created and leaves out the order lines', async () => {
    callsMock.mockResolvedValue({ items: [makeCall()], total: 1, limit: 25, skip: 0 })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
    })
    const wrapper = mountWithApp(AgentCallsTable, { global: { plugins: [router] } })
    await flushPromises()

    const links = wrapper.findAll('a')
    expect(links).toHaveLength(1)
    expect(links[0]!.attributes('href')).toBe(`/resolve/${ORDER_ID}`)
    expect(links[0]!.text()).toBe(t('agents.calls.kinds.order'))
    expect(wrapper.text()).toContain(t('agents.calls.outcomes.ok'))
    expect(wrapper.text()).toContain('supplier_id: 4')
    wrapper.unmount()
  })
})
