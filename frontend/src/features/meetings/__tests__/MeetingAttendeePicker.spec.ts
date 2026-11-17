import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import AutoComplete from 'openvue/autocomplete'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { PageResponse } from '@/core/api/types'
import type { UserSummary } from '@/core/types/userResponse'
import type { AttendeeDraft } from '../utils/attendees'

vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: () => false }),
}))

function user(id: number, fullName: string, extra: Partial<UserSummary> = {}): UserSummary {
  return {
    id,
    username: fullName.toLowerCase().replace(' ', '.'),
    full_name: fullName,
    is_active: true,
    is_systemuser: false,
    is_service_account: false,
    is_shared_account: false,
    has_avatar: false,
    ...extra,
  } as UserSummary
}

const getUserDirectory = vi.fn<() => Promise<PageResponse<UserSummary>>>().mockResolvedValue({
  items: [
    user(1, 'Anna Generic'),
    user(2, 'Andreas Wildcard', { is_active: false }),
    user(3, 'Anlagen Key', { is_service_account: true }),
    user(4, 'Jonas Example'),
  ],
  total: 4,
  limit: 100,
  skip: 0,
})
vi.mock('@/core/api/users/getUserDirectory', () => ({ getUserDirectory: () => getUserDirectory() }))

import MeetingAttendeePicker from '../components/MeetingAttendeePicker.vue'

describe('MeetingAttendeePicker', () => {
  it('offers the active people among the users on the first search, with their picture', async () => {
    const attendees: AttendeeDraft[] = []
    const wrapper = mountWithApp(MeetingAttendeePicker, { props: { modelValue: attendees } })

    wrapper.findComponent(AutoComplete).vm.$emit('complete', { query: 'an', originalEvent: new Event('input') })
    await flushPromises()

    const groups = wrapper.findComponent(AutoComplete).props('suggestions') as {
      items: { type: string; label: string }[]
    }[]
    const users = groups[0]?.items.filter((item) => item.type === 'user').map((item) => item.label)
    expect(users).toEqual(['Anna Generic'])
  })

  it('shows a user attendee with their avatar instead of the generic icon', async () => {
    const attendees: AttendeeDraft[] = [
      {
        key: 'user:4',
        kind: 'user',
        status: 'present',
        userId: 4,
        contactId: null,
        attendeeId: null,
        name: 'Jonas Example',
        email: null,
        detail: null,
      },
    ]
    const wrapper = mountWithApp(MeetingAttendeePicker, { props: { modelValue: attendees } })
    await flushPromises()

    const row = wrapper.get('[data-testid="meeting-attendee-list"] li')
    expect(row.find('.user-avatar-preview-bubble').exists()).toBe(true)
    expect(row.find('[data-testid="meeting-attendee-kind-icon"]').exists()).toBe(false)
  })
})
