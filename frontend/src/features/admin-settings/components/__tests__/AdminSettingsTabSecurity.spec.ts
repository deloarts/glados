import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'

import type { AdminSecuritySettings, AllAdminSettings } from '../../types/adminSettingsTypes'

// No spec covered this tab before. This establishes one, mirroring the
// mount/user-fixture pattern shared by the other AdminSettingsTab*.spec.ts
// files. Scoped to the new token-lifetime-cap field and the tab's new
// Authentication / Password & Session Policy section grouping (the tab had
// no headings at all before, so there is no prior structure to disturb).

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import AdminSettingsTabSecurity from '../AdminSettingsTabSecurity.vue'

function makeSecuritySettings(
  overrides: Partial<AdminSecuritySettings> = {},
): AdminSecuritySettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    enforce_totp: false,
    allow_rfid_login: true,
    allow_local_login: true,
    enable_api_key_auth: false,
    min_password_length: 8,
    session_timeout_minutes: 1440,
    totp_trusted_device_days: 30,
    max_login_attempts: 0,
    lockout_duration_minutes: 15,
    token_max_lifetime_days: 3650,
    session_max_lifetime_days: 30,
    enable_terminals: true,
    enable_infoscreen_weather: true,
    terminal_allowed_ips: [],
    ...overrides,
  }
}

async function mountTab(permissions: string[], security: AdminSecuritySettings) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  useAdminSettingsStore().settings = { security } as unknown as AllAdminSettings

  const wrapper = mountWithApp(AdminSettingsTabSecurity, {
    pinia,
    attachTo: document.body,
    global: {
      plugins: [ConfirmationService],
    },
  })
  await flushPromises()
  return wrapper
}

function fieldRow(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('.field-row').find((r) => r.text().includes(label))!
}

function tokenCapInput(wrapper: ReturnType<typeof mount>) {
  const label = i18n.global.t('adminSettings.security.tokenMaxLifetimeDays') as string
  return fieldRow(wrapper, label).findComponent({ name: 'InputNumber' })
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('AdminSettingsTabSecurity', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('groups its fields under Authentication and Password & Session Policy headings', async () => {
    const wrapper = await mountTab(['write:settings'], makeSecuritySettings())

    const labels = wrapper.findAll('.section-label').map((el) => el.text())
    expect(labels).toEqual([
      i18n.global.t('adminSettings.security.authenticationSection'),
      i18n.global.t('adminSettings.security.policySection'),
    ])

    wrapper.unmount()
  })

  it('reflects settings.security.token_max_lifetime_days', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeSecuritySettings({ token_max_lifetime_days: 365 }),
    )

    expect(tokenCapInput(wrapper).props('modelValue')).toBe(365)

    wrapper.unmount()
  })

  it('PUTs token_max_lifetime_days with the rest of the security form on Save', async () => {
    putMock.mockResolvedValue({ data: makeSecuritySettings({ token_max_lifetime_days: 365 }) })
    const wrapper = await mountTab(['write:settings'], makeSecuritySettings())

    await tokenCapInput(wrapper).vm.$emit('update:modelValue', 365)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/security',
      expect.objectContaining({ token_max_lifetime_days: 365 }),
    )

    wrapper.unmount()
  })
  it('lets the token cap go down to 0, which lifts it', async () => {
    const wrapper = await mountTab(['write:settings'], makeSecuritySettings())

    expect(tokenCapInput(wrapper).props('min')).toBe(0)

    wrapper.unmount()
  })

  it('refuses an idle timeout of 0 and PUTs the absolute session lifetime', async () => {
    putMock.mockResolvedValue({ data: makeSecuritySettings({ session_max_lifetime_days: 7 }) })
    const wrapper = await mountTab(['write:settings'], makeSecuritySettings())
    const idle = fieldRow(
      wrapper,
      i18n.global.t('adminSettings.security.sessionTimeoutMinutes') as string,
    ).findComponent({ name: 'InputNumber' })
    const lifetime = fieldRow(
      wrapper,
      i18n.global.t('adminSettings.security.sessionMaxLifetimeDays') as string,
    ).findComponent({ name: 'InputNumber' })

    expect(idle.props('min')).toBe(1)
    await lifetime.vm.$emit('update:modelValue', 7)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/security',
      expect.objectContaining({ session_max_lifetime_days: 7 }),
    )

    wrapper.unmount()
  })
})
