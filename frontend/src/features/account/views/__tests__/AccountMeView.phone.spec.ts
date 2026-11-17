import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { stubPhoneScreen } from '@/test-utils/phoneScreen'
import { makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { i18n } from '@/core/i18n'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import AccountMeView from '../AccountMeView.vue'

const t = i18n.global.t

describe('AccountMeView on a phone', () => {
  beforeEach(() => {
    stubPhoneScreen(true)
  })

  it('keeps Save and the theme, and leaves the rest of the settings to the desktop', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = makeUserResponse()

    const wrapper = mountWithApp(AccountMeView, { pinia })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain(t('common.save'))
    expect(text).toContain(t('accountMe.theme.preset'))
    expect(text).not.toContain(t('accountMe.profile.fullName'))
    expect(text).not.toContain(t('accountMe.avatar.title'))
    expect(text).not.toContain(t('accountMe.password.changeButton'))
    expect(text).not.toContain(t('accountMe.visualAids.tableGridlines'))

    wrapper.unmount()
  })
})
