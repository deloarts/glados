import { afterEach, describe, expect, it } from 'vitest'

import ContactLinks from '../ContactLinks.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { stubPhoneScreen } from '@/test-utils/phoneScreen'

afterEach(() => {
  stubPhoneScreen(false)
})

describe('ContactLinks', () => {
  it('links the e-mail address and keeps the phone number to a phone', () => {
    stubPhoneScreen(false)
    const wrapper = mountWithApp(ContactLinks, {
      props: { email: 'buyer@example.com', phone: '+43 1 234 56' },
    })

    const links = wrapper.findAll('a')
    expect(links.map((a) => a.attributes('href'))).toEqual(['mailto:buyer@example.com'])

    wrapper.unmount()
  })

  it('adds the phone number as a call link on a phone', () => {
    stubPhoneScreen(true)
    const wrapper = mountWithApp(ContactLinks, {
      props: { email: 'buyer@example.com', phone: '+43 1 234 56' },
    })

    expect(wrapper.findAll('a').map((a) => a.attributes('href'))).toEqual([
      'mailto:buyer@example.com',
      'tel:+43123456',
    ])

    wrapper.unmount()
  })

  it('shows the empty placeholder without any contact data', () => {
    stubPhoneScreen(true)
    const wrapper = mountWithApp(ContactLinks, { props: { email: null, phone: null } })

    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.find('.text-muted').exists()).toBe(true)

    wrapper.unmount()
  })
})
