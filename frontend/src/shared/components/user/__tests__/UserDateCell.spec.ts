import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'

vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: async () => ({
    items: [{ id: 3, username: 'adm', full_name: 'Ada Admin', email: 'ada@example.com', has_avatar: false }],
    total: 1,
  }),
}))

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { makeUserResponse } from '@/test-utils/factories'
import UserDateCell from '../UserDateCell.vue'
import type { UserResponse } from '@/core/types/userResponse'

async function mountCell(props: { date: string | null; userId?: number; user?: UserResponse; name?: string }) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(UserDateCell, { pinia, props })
  await flushPromises()
  return wrapper
}

describe('UserDateCell', () => {
  it('shows the date above the person, whose card opens from the name', async () => {
    const wrapper = await mountCell({ date: '2026-10-28T09:00:00Z', userId: 3, name: 'Old Name' })
    const lines = wrapper.find('.user-date-cell').element.children
    expect(lines).toHaveLength(2)
    expect(wrapper.find('.user-avatar-preview-name').text()).toBe('Ada Admin')
  })

  it('falls back to the name the record keeps when the user is not listed', async () => {
    const wrapper = await mountCell({ date: '2026-10-28T09:00:00Z', userId: 99, name: 'Former Colleague' })
    expect(wrapper.text()).toContain('Former Colleague')
  })

  it('shows the user the record embeds when the user list has no entry', async () => {
    const wrapper = await mountCell({
      date: '2026-10-28T09:00:00Z',
      user: makeUserResponse({ id: 42, full_name: 'Embedded Person' }),
    })
    expect(wrapper.find('.user-avatar-preview-name').text()).toBe('Embedded Person')
  })

  it('prefers the listed user over the embedded one', async () => {
    const wrapper = await mountCell({
      date: '2026-10-28T09:00:00Z',
      user: makeUserResponse({ id: 3, full_name: 'Stale Name' }),
    })
    expect(wrapper.find('.user-avatar-preview-name').text()).toBe('Ada Admin')
  })

  it('shows the empty placeholder as the second line when no person is known', async () => {
    const wrapper = await mountCell({ date: '2026-10-28T09:00:00Z' })
    const lines = wrapper.find('.user-date-cell').element.children
    expect(lines).toHaveLength(2)
    expect(lines[1]?.textContent).toBe(getEmptyPlaceholder())
  })

  it('shows the empty placeholder without a date', async () => {
    const wrapper = await mountCell({ date: null, userId: 3 })
    expect(wrapper.find('.user-date-cell').exists()).toBe(false)
  })
})
