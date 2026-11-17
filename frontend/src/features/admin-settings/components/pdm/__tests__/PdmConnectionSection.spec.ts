import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { formatISODateTime } from '@/core/utils/dates'
import PdmConnectionSection from '../PdmConnectionSection.vue'
import type { PdmSession } from '../../../types/adminSettingsTypes'

const NO_SESSION: PdmSession = { active: false, obtained_at: null, user_id: null }
const ACTIVE_SESSION: PdmSession = {
  active: true,
  obtained_at: '2026-09-01T10:00:00Z',
  user_id: 7,
}

function mountSection(overrides: {
  canWrite?: boolean
  enabled?: boolean
  passwordConfigured?: boolean
  session?: PdmSession
} = {}) {
  return mountWithApp(PdmConnectionSection, {
    props: {
      enabled: overrides.enabled ?? false,
      baseUrl: 'http://pdm.example.com:65453',
      vaultName: 'MainVault',
      username: 'glados-service',
      password: '',
      verifyCertificate: true,
      timeoutSeconds: 15,
      canWrite: overrides.canWrite ?? true,
      passwordConfigured: overrides.passwordConfigured ?? false,
      session: overrides.session ?? NO_SESSION,
    },
  })
}

describe('PdmConnectionSection', () => {
  it('renders the connection fields with their current values', () => {
    const wrapper = mountSection()

    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.solidworksPdm.pdm.connectionSection'))
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.solidworksPdm.pdm.baseUrl'))
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.solidworksPdm.pdm.vaultName'))
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.solidworksPdm.pdm.username'))

    const inputs = wrapper.findAllComponents({ name: 'InputText' })
    const values = inputs.map((input) => input.props('modelValue'))
    expect(values).toContain('http://pdm.example.com:65453')
    expect(values).toContain('MainVault')
    expect(values).toContain('glados-service')

    wrapper.unmount()
  })

  // The global enable toggle governs the whole PDM integration, not just
  // the sync section, so it renders live here, right under the connection
  // section header, ahead of the connection fields it is also a
  // prerequisite for.
  it('renders the "Enable PDM integration" toggle directly under the section header', () => {
    const wrapper = mountSection({ enabled: true })

    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.solidworksPdm.pdm.sync.enabled'))
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.solidworksPdm.pdm.sync.enabledHint'))

    const toggles = wrapper.findAllComponents({ name: 'ToggleSwitch' })
    expect(toggles[0]!.props('modelValue')).toBe(true)

    wrapper.unmount()
  })

  it('emits update:enabled when the toggle is changed', async () => {
    const wrapper = mountSection({ enabled: false })

    const toggles = wrapper.findAllComponents({ name: 'ToggleSwitch' })
    await toggles[0]!.vm.$emit('update:modelValue', true)

    expect(wrapper.emitted('update:enabled')).toEqual([[true]])

    wrapper.unmount()
  })

  it('disables every editable field without write:settings', () => {
    const wrapper = mountSection({ canWrite: false })

    for (const input of wrapper.findAllComponents({ name: 'InputText' })) {
      expect(input.props('disabled')).toBe(true)
    }
    for (const input of wrapper.findAllComponents({ name: 'InputNumber' })) {
      expect(input.props('disabled')).toBe(true)
    }
    // The two toggles left in this section: "Enable PDM integration" and
    // "Verify certificate".
    const toggles = wrapper.findAllComponents({ name: 'ToggleSwitch' })
    expect(toggles).toHaveLength(2)
    for (const toggle of toggles) {
      expect(toggle.props('disabled')).toBe(true)
    }

    wrapper.unmount()
  })

  it('enables editable fields with write:settings', () => {
    const wrapper = mountSection({ canWrite: true })

    const baseUrlInput = wrapper
      .findAllComponents({ name: 'InputText' })
      .find((input) => input.props('modelValue') === 'http://pdm.example.com:65453')!
    expect(baseUrlInput.props('disabled')).toBe(false)

    wrapper.unmount()
  })

  it('shows the "enter password" placeholder when no password is configured', () => {
    const wrapper = mountSection({ passwordConfigured: false })

    const passwordInput = wrapper.find('input[type="password"]')
    expect(passwordInput.attributes('placeholder')).toBe(
      i18n.global.t('adminSettings.solidworksPdm.pdm.passwordPlaceholder'),
    )

    wrapper.unmount()
  })

  it('shows the "leave blank to keep" placeholder when a password is already configured', () => {
    const wrapper = mountSection({ passwordConfigured: true })

    const passwordInput = wrapper.find('input[type="password"]')
    expect(passwordInput.attributes('placeholder')).toBe(
      i18n.global.t('adminSettings.solidworksPdm.pdm.passwordConfigured'),
    )

    wrapper.unmount()
  })

  it('shows "no session" when the session is inactive', () => {
    const wrapper = mountSection({ session: NO_SESSION })

    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.solidworksPdm.pdm.sessionNone'))

    wrapper.unmount()
  })

  it('shows "session active since" with the formatted date when a session is active', () => {
    const wrapper = mountSection({ session: ACTIVE_SESSION })

    expect(wrapper.text()).not.toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sessionNone'),
    )
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sessionActiveSince', {
        date: formatISODateTime(ACTIVE_SESSION.obtained_at!),
      }),
    )

    wrapper.unmount()
  })

  it('emits update:baseUrl when the base URL field changes', async () => {
    const wrapper = mountSection()

    const baseUrlInput = wrapper
      .findAllComponents({ name: 'InputText' })
      .find((input) => input.props('modelValue') === 'http://pdm.example.com:65453')!
    await baseUrlInput.vm.$emit('update:modelValue', 'https://new-host:65453')
    await flushPromises()

    expect(wrapper.emitted('update:baseUrl')).toEqual([['https://new-host:65453']])

    wrapper.unmount()
  })
})
