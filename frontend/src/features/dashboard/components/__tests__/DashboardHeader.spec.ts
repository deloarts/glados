import { describe, it, expect, vi, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import enGB from '@/core/i18n/locales/en-GB'

import DashboardHeader from '../DashboardHeader.vue'

import type { UserResponse } from '@/core/types/userResponse'

function mountHeader() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mountWithApp(DashboardHeader, { pinia })
}

describe('DashboardHeader', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows a greeting phrase from the current time bucket', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 7, 11, 10, 0))

    const wrapper = mountHeader()

    const greetingText = wrapper.find('.dashboard-header-greeting').text()
    expect(enGB.dashboard.greeting.morning).toContain(greetingText)
  })

  it("appends the user's first name after the greeting when signed in", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 7, 11, 10, 0))
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = { full_name: 'Jane Doe' } as unknown as UserResponse

    const wrapper = mountWithApp(DashboardHeader, { pinia })

    expect(wrapper.find('.dashboard-header-greeting').text()).toContain(', Jane')
  })

  it('omits the trailing name entirely when no user is signed in', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 7, 11, 10, 0))

    const wrapper = mountHeader()

    expect(wrapper.find('.dashboard-header-greeting').text()).not.toContain(',')
  })

  it("falls back to 'Glados' when no branding has loaded", () => {
    const wrapper = mountHeader()

    expect(wrapper.find('.dashboard-header-subtitle').text()).toContain('Glados')
  })
})
