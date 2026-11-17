import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'

import type { PageResponse } from '@/core/api/types'
import type { SecurityEventsParams } from '../../api/getSecurityEvents'
import type { SecurityEvent } from '../../types/adminSettingsTypes'

const getSecurityEventsMock =
  vi.fn<(params?: SecurityEventsParams) => Promise<PageResponse<SecurityEvent>>>()

vi.mock('../../api/getSecurityEvents', () => ({
  getSecurityEvents: (params?: SecurityEventsParams) => getSecurityEventsMock(params),
}))

import AdminSettingsTabSecurityLog from '../AdminSettingsTabSecurityLog.vue'

const FAILED_LOGIN: SecurityEvent = {
  id: 1,
  public_id: '00000000-0000-0000-0000-000000000001',
  occurred_at: '2026-11-04T08:00:00Z',
  event_type: 'login',
  outcome: 'failure',
  actor_user_id: 5,
  actor_username: 'alice',
  target_user_id: 5,
  target_username: 'alice',
  target_id: null,
  client_ip: '10.0.0.7',
  user_agent: 'Firefox',
  detail: { method: 'password', reason: 'invalid_credentials' },
}

describe('AdminSettingsTabSecurityLog', () => {
  beforeEach(() => {
    vi.useRealTimers()
    getSecurityEventsMock.mockReset()
    getSecurityEventsMock.mockResolvedValue({ items: [], total: 0, limit: 25, skip: 0 })
  })

  it('loads the first page unfiltered', async () => {
    const wrapper = mountWithApp(AdminSettingsTabSecurityLog)
    await flushPromises()

    expect(wrapper.findComponent({ name: 'DataTable' }).props('filterDisplay')).toBe('row')
    expect(wrapper.findComponent({ name: 'UserDateFilter' }).exists()).toBe(true)
    expect(getSecurityEventsMock).toHaveBeenCalledWith({ skip: 0, limit: 25 })
  })

  it('refetches at once with the picked event type and outcome', async () => {
    const wrapper = mountWithApp(AdminSettingsTabSecurityLog)
    await flushPromises()
    getSecurityEventsMock.mockClear()

    const [typeSelect, outcomeSelect] = wrapper.findAllComponents({ name: 'Select' })
    await typeSelect!.vm.$emit('update:modelValue', 'login')
    await outcomeSelect!.vm.$emit('update:modelValue', 'failure')
    await flushPromises()

    expect(getSecurityEventsMock).toHaveBeenLastCalledWith({
      skip: 0,
      limit: 25,
      event_type: 'login',
      outcome: 'failure',
    })
  })

  it('filters at once by the person picked in the first column', async () => {
    const wrapper = mountWithApp(AdminSettingsTabSecurityLog)
    await flushPromises()
    getSecurityEventsMock.mockClear()

    await wrapper.findComponent({ name: 'UserDateFilter' }).vm.$emit('update:userId', 5)
    await flushPromises()

    expect(getSecurityEventsMock).toHaveBeenCalledWith({ skip: 0, limit: 25, user_id: 5 })
  })

  it('shows an event with its translated type and details', async () => {
    getSecurityEventsMock.mockResolvedValue({ items: [FAILED_LOGIN], total: 1, limit: 25, skip: 0 })

    const wrapper = mountWithApp(AdminSettingsTabSecurityLog)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Sign-in')
    expect(text).toContain('Failure')
    expect(text).toContain('Method: Password · Reason: Wrong credentials')
    expect(text).toContain('10.0.0.7')
  })
})
