import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import Tooltip from 'openvue/tooltip'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'
import AppFooter from '../AppFooter.vue'
import { useConnectionStore } from '@/core/stores/connectionStore'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { APERTURE_FOOTER, useEasterEggs } from '@/core/composables/useEasterEggs'

function mountFooter() {
  return mount(AppFooter, {
    global: {
      plugins: [[OpenVue, { theme: { preset: Aura } }], i18n],
      directives: { tooltip: Tooltip },
      // Pulls in the whole cake protocol otherwise, which is not what this
      // file is about.
      stubs: { CakeEasterEgg: true },
    },
  })
}

describe('AppFooter, aperture branding override', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEasterEggs().setAperture(false)
  })

  it('shows the deployment’s own footer text normally', () => {
    usePublicBrandingStore().branding = {
      app_name: 'Acme Works',
      app_description: null,
      footer_text: 'Acme Works Ltd',
      company_name: null,
      contact_email: null,
      support_url: null,
      imprint_url: null,
      privacy_url: null,
      has_logo: false,
      has_favicon: false,
      has_login_background_video: false,
      default_language: 'enGB',
      maintenance_enabled: false,
      maintenance_message: null,
    }

    expect(mountFooter().text()).toContain('Acme Works Ltd')
  })

  it('shows the company name on the left when one is configured', () => {
    usePublicBrandingStore().branding = {
      app_name: 'Acme Works',
      app_description: null,
      footer_text: 'Acme Works Ltd',
      company_name: 'Acme',
      contact_email: null,
      support_url: null,
      imprint_url: null,
      privacy_url: null,
      has_logo: false,
      has_favicon: false,
      has_login_background_video: false,
      default_language: 'enGB',
      maintenance_enabled: false,
      maintenance_message: null,
    }

    expect(mountFooter().find('.company-name').text()).toBe('Acme')
  })

  it('leaves the left slot empty when no company name is set', () => {
    // Rather than falling back to the app name, which is already centred.
    usePublicBrandingStore().branding = {
      app_name: 'Acme Works',
      app_description: null,
      footer_text: 'Acme Works Ltd',
      company_name: null,
      contact_email: null,
      support_url: null,
      imprint_url: null,
      privacy_url: null,
      has_logo: false,
      has_favicon: false,
      has_login_background_video: false,
      default_language: 'enGB',
      maintenance_enabled: false,
      maintenance_message: null,
    }

    expect(mountFooter().find('.company-name').exists()).toBe(false)
  })

  it('hides the company name in aperture mode', async () => {
    usePublicBrandingStore().branding = {
      app_name: 'Acme Works',
      app_description: null,
      footer_text: 'Acme Works Ltd',
      company_name: 'Acme',
      contact_email: null,
      support_url: null,
      imprint_url: null,
      privacy_url: null,
      has_logo: false,
      has_favicon: false,
      has_login_background_video: false,
      default_language: 'enGB',
      maintenance_enabled: false,
      maintenance_message: null,
    }
    useEasterEggs().setAperture(true)

    const footer = mountFooter()
    await footer.vm.$nextTick()

    expect(footer.find('.company-name').exists()).toBe(false)
  })

  // A customer's own footer text would rather defeat the point of the joke.
  it('overrides it in aperture mode, whatever is configured', async () => {
    usePublicBrandingStore().branding = {
      app_name: 'Acme Works',
      app_description: null,
      footer_text: 'Acme Works Ltd',
      company_name: null,
      contact_email: null,
      support_url: null,
      imprint_url: null,
      privacy_url: null,
      has_logo: false,
      has_favicon: false,
      has_login_background_video: false,
      default_language: 'enGB',
      maintenance_enabled: false,
      maintenance_message: null,
    }
    useEasterEggs().setAperture(true)

    const wrapper = mountFooter()

    expect(wrapper.text()).toContain(APERTURE_FOOTER)
    expect(wrapper.text()).not.toContain('Acme Works Ltd')
  })

  it('reverts as soon as aperture mode is switched off', async () => {
    usePublicBrandingStore().branding = {
      app_name: 'Acme Works',
      app_description: null,
      footer_text: 'Acme Works Ltd',
      company_name: null,
      contact_email: null,
      support_url: null,
      imprint_url: null,
      privacy_url: null,
      has_logo: false,
      has_favicon: false,
      has_login_background_video: false,
      default_language: 'enGB',
      maintenance_enabled: false,
      maintenance_message: null,
    }
    const { setAperture } = useEasterEggs()
    setAperture(true)
    const wrapper = mountFooter()

    setAperture(false)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Acme Works Ltd')
    expect(wrapper.text()).not.toContain(APERTURE_FOOTER)
  })
})

// The General tab's "Contact & Legal" fields show up exactly here: as a
// Contact | Support | Imprint | Privacy row to the right of the company name,
// only for the ones that are set, and never in aperture mode.
describe('AppFooter, contact & legal links', () => {
  function setBranding(
    overrides: Partial<{
      company_name: string | null
      contact_email: string | null
      support_url: string | null
      imprint_url: string | null
      privacy_url: string | null
    }> = {},
  ) {
    usePublicBrandingStore().branding = {
      app_name: 'Acme Works',
      app_description: null,
      footer_text: 'Acme Works Ltd',
      company_name: null,
      contact_email: null,
      support_url: null,
      imprint_url: null,
      privacy_url: null,
      has_logo: false,
      has_favicon: false,
      has_login_background_video: false,
      default_language: 'enGB',
      maintenance_enabled: false,
      maintenance_message: null,
      ...overrides,
    }
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    useEasterEggs().setAperture(false)
  })

  it('renders no link row, and no left slot at all, when nothing is configured', () => {
    setBranding()

    const wrapper = mountFooter()

    expect(wrapper.find('.footer-links').exists()).toBe(false)
    expect(wrapper.find('.footer-left').exists()).toBe(false)
  })

  it('renders the configured links in order, next to the company name', () => {
    setBranding({
      company_name: 'Acme',
      contact_email: 'office@example.com',
      support_url: 'https://example.com/support',
      imprint_url: 'https://example.com/imprint',
      privacy_url: 'https://example.com/privacy',
    })

    const left = mountFooter().find('.footer-left')
    const links = left.findAll('.footer-link')

    expect(left.find('.company-name').text()).toBe('Acme')
    expect(links.map((a) => a.text())).toEqual(['Contact', 'Support', 'Imprint', 'Privacy'])
    expect(links.map((a) => a.attributes('href'))).toEqual([
      'mailto:office@example.com',
      'https://example.com/support',
      'https://example.com/imprint',
      'https://example.com/privacy',
    ])
  })

  it('opens URLs in a new tab but hands mailto: straight to the mail client', () => {
    setBranding({ contact_email: 'office@example.com', privacy_url: 'https://example.com/p' })

    const links = mountFooter().findAll('.footer-link')

    expect(links[0]!.attributes('target')).toBeUndefined()
    expect(links[1]!.attributes('target')).toBe('_blank')
    expect(links[1]!.attributes('rel')).toBe('noopener noreferrer')
  })

  it('shows only the ones that are set, still without a company name', () => {
    setBranding({ imprint_url: 'https://example.com/imprint' })

    const wrapper = mountFooter()

    expect(wrapper.find('.company-name').exists()).toBe(false)
    expect(wrapper.findAll('.footer-link').map((a) => a.text())).toEqual(['Imprint'])
  })

  it('hides the link row in aperture mode', async () => {
    setBranding({ company_name: 'Acme', imprint_url: 'https://example.com/imprint' })
    useEasterEggs().setAperture(true)

    const wrapper = mountFooter()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.footer-links').exists()).toBe(false)
    expect(wrapper.find('.footer-left').exists()).toBe(false)
  })

  it('renders a safe https link with an href', () => {
    setBranding({ support_url: 'https://example.com/support' })

    const link = mountFooter().find('.footer-link')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('https://example.com/support')
  })

  it('renders the contact email as a mailto: href', () => {
    setBranding({ contact_email: 'office@example.com' })

    const link = mountFooter().find('.footer-link')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('mailto:office@example.com')
  })

  // A branding field predating client-side URL validation could in theory
  // still hold something unsafe: the link is dropped entirely rather than
  // rendered without an href or with a live href pointing at it.
  it('drops a link whose href is unsafe, rather than rendering it', () => {
    setBranding({ imprint_url: 'javascript:alert(1)', privacy_url: 'https://example.com/privacy' })

    const wrapper = mountFooter()
    const links = wrapper.findAll('.footer-link')

    expect(links).toHaveLength(1)
    expect(links[0]!.attributes('href')).toBe('https://example.com/privacy')
    expect(wrapper.text()).not.toContain('javascript:')
  })
})

// The offline state lives in the footer rather than a blocking modal. The
// footer is on screen at all times, so this is visible without trapping the
// user behind a dialog
// they cannot dismiss, and it is never on the login page, because AppFooter
// only exists inside AppLayout.
describe('AppFooter, offline state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEasterEggs().setAperture(false)
    usePublicBrandingStore().branding = {
      app_name: 'Acme Works',
      app_description: null,
      footer_text: 'Acme Works Ltd',
      company_name: null,
      contact_email: null,
      support_url: null,
      imprint_url: null,
      privacy_url: null,
      has_logo: false,
      has_favicon: false,
      has_login_background_video: false,
      default_language: 'enGB',
      maintenance_enabled: false,
      maintenance_message: null,
    }
  })

  it('shows nothing about the connection while it is healthy', () => {
    const wrapper = mountFooter()

    expect(wrapper.find('.offline-status').exists()).toBe(false)
    expect(wrapper.find('.footer').classes()).not.toContain('is-offline')
  })

  it('takes over the footer once the connection is lost', async () => {
    const connectionStore = useConnectionStore()
    const wrapper = mountFooter()

    connectionStore.isOffline = true
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.footer').classes()).toContain('is-offline')
    expect(wrapper.text()).toContain('No connection to the server')
    // The branding text is what the offline message replaces.
    expect(wrapper.text()).not.toContain('Acme Works Ltd')
  })

  // role="alert" (rather than role="status") because losing the connection
  // is urgent enough to interrupt whatever a screen reader is announcing,
  // unlike the polite live regions used for routine progress text elsewhere.
  it('announces the offline message as an assertive alert', async () => {
    const connectionStore = useConnectionStore()
    const wrapper = mountFooter()

    connectionStore.isOffline = true
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.offline-status').attributes('role')).toBe('alert')
  })

  it('offers a manual retry that probes the server', async () => {
    const connectionStore = useConnectionStore()
    const retryNow = vi.spyOn(connectionStore, 'retryNow').mockImplementation(() => {})
    const wrapper = mountFooter()
    connectionStore.isOffline = true
    await wrapper.vm.$nextTick()

    await wrapper.find('.offline-retry').trigger('click')

    expect(retryNow).toHaveBeenCalledOnce()
  })

  it('disables the retry while a probe is already in flight', async () => {
    const connectionStore = useConnectionStore()
    const wrapper = mountFooter()
    connectionStore.isOffline = true
    connectionStore.isProbing = true
    await wrapper.vm.$nextTick()

    const retry = wrapper.find('.offline-retry')
    expect(retry.attributes('disabled')).toBeDefined()
    expect(retry.text()).toBe('Reconnecting…')
  })

  it('puts the branding back the moment the connection returns', async () => {
    const connectionStore = useConnectionStore()
    const wrapper = mountFooter()
    connectionStore.isOffline = true
    await wrapper.vm.$nextTick()

    connectionStore.isOffline = false
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.offline-status').exists()).toBe(false)
    expect(wrapper.text()).toContain('Acme Works Ltd')
  })
})
