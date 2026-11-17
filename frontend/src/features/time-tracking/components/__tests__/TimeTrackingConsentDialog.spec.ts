import { describe, it, expect, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import TimeTrackingConsentDialog from '../TimeTrackingConsentDialog.vue'

const t = i18n.global.t

type Props = {
  visible: boolean
  providerName: string
  privacyPolicyUrl: string | null
}

function mountDialog(overrides: Partial<Props> = {}) {
  return mountWithApp(TimeTrackingConsentDialog, {
    attachTo: document.body,
    props: {
      visible: true,
      providerName: 'Example Time',
      privacyPolicyUrl: null,
      ...overrides,
    },
  })
}

function confirmButton(): HTMLButtonElement {
  return document.body.querySelector<HTMLButtonElement>(
    '[data-testid="time-tracking-consent-confirm"]',
  )!
}

describe('TimeTrackingConsentDialog', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('names what is read, that nothing is stored, that the password is sealed, and how to withdraw', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    const text = document.body.textContent ?? ''
    expect(text).toContain(t('timeTracking.consent.intro', { provider: 'Example Time' }))
    expect(text).toContain(t('timeTracking.consent.readOnRequest'))
    expect(text).toContain(t('timeTracking.consent.nothingStored'))
    expect(text).toContain(t('timeTracking.consent.encrypted'))
    expect(text).toContain(t('timeTracking.consent.sealed'))
    expect(text).toContain(t('timeTracking.consent.adminsCannotSee'))
    expect(text).toContain(t('timeTracking.consent.withdraw'))

    wrapper.unmount()
  })

  it('only confirms once the checkbox is ticked', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    expect(confirmButton().disabled).toBe(true)

    document.body
      .querySelector<HTMLInputElement>('[data-testid="time-tracking-consent-agree"]')!
      .click()
    await flushPromises()

    expect(confirmButton().disabled).toBe(false)
    confirmButton().click()
    await flushPromises()

    expect(wrapper.emitted('confirm')).toHaveLength(1)

    wrapper.unmount()
  })

  it('links the privacy policy only when it is a safe http(s) URL', async () => {
    const wrapper = mountDialog({ privacyPolicyUrl: 'https://intranet.example.test/privacy' })
    await flushPromises()

    const link = document.body.querySelector<HTMLAnchorElement>('a[target="_blank"]')
    expect(link?.getAttribute('href')).toBe('https://intranet.example.test/privacy')
    expect(link?.getAttribute('rel')).toContain('noopener')

    wrapper.unmount()
    document.body.innerHTML = ''

    const unsafe = mountDialog({ privacyPolicyUrl: 'javascript:alert(1)' })
    await flushPromises()
    expect(document.body.querySelector('a[target="_blank"]')).toBeNull()

    unsafe.unmount()
  })
})
