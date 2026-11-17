import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'

import type { AdminSecuritySettings, AllAdminSettings } from '../../types/adminSettingsTypes'

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
    terminal_allowed_ips: ['10.0.0.0/8'],
    ...overrides,
  }
}

let wrapper: VueWrapper | null = null

async function mountTab(permissions: string[], security: AdminSecuritySettings) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  useAdminSettingsStore().settings = { security } as unknown as AllAdminSettings

  wrapper = mountWithApp(AdminSettingsTabSecurity, {
    pinia,
    attachTo: document.body,
    global: { plugins: [ConfirmationService] },
  })
  await flushPromises()
  return wrapper
}

function saveButton(w: VueWrapper) {
  return w
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('AdminSettingsTabSecurity terminals', () => {
  beforeEach(() => {
    putMock.mockReset()
    wrapper?.unmount()
    wrapper = null
  })

  it('shows the stored allowlist and the proxy hint', async () => {
    const w = await mountTab(['write:settings'], makeSecuritySettings())

    expect(w.get('[data-testid="security-terminal-ips"]').text()).toContain('10.0.0.0/8')
    expect(w.text()).toContain(i18n.global.t('adminSettings.security.terminalAllowedIpsProxyHint'))
  })

  it('adds an address and sends the terminal fields on Save', async () => {
    putMock.mockResolvedValue({ data: makeSecuritySettings() })
    const w = await mountTab(['write:settings'], makeSecuritySettings())

    await w.get('[data-testid="security-terminal-ip-input"]').setValue('192.168.10.0/24')
    await w.get('[data-testid="security-terminal-ip-add"]').trigger('click')
    await saveButton(w).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/security',
      expect.objectContaining({
        enable_terminals: true,
        terminal_allowed_ips: ['10.0.0.0/8', '192.168.10.0/24'],
      }),
    )
  })

  it('refuses an entry that cannot be an address', async () => {
    const w = await mountTab(['write:settings'], makeSecuritySettings())

    await w.get('[data-testid="security-terminal-ip-input"]').setValue('not an ip')
    await w.get('[data-testid="security-terminal-ip-add"]').trigger('click')

    expect(w.get('[data-testid="security-terminal-ips"]').text()).not.toContain('not an ip')
  })

  it('keeps the fields read only without write:settings', async () => {
    const w = await mountTab(['read:settings'], makeSecuritySettings())

    const toggle = w
      .findAllComponents({ name: 'ToggleSwitch' })
      .find((c) => c.attributes('data-testid') === 'security-enable-terminals')!
    expect(toggle.props('disabled')).toBe(true)
    expect(w.get('[data-testid="security-terminal-ip-input"]').attributes('disabled')).toBeDefined()
    const add = w.get('[data-testid="security-terminal-ip-add"]')
    expect(add.attributes('disabled')).toBeDefined()
    const row = add.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(row?.$_ptooltipValue).toBe('This needs the permission Write Settings.')
    expect(saveButton(w).attributes('disabled')).toBeDefined()
  })
})
