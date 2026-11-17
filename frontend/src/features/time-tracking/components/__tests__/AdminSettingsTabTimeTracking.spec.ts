import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'
import type { ToastMessageOptions } from 'openvue/toast'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'
import type { UserResponse } from '@/core/types/userResponse'
import type {
  AdminTimeTrackingSettings,
  ConfirmTimeTrackingKeyCommand,
  PurgeTimeTrackingCredentialsResult,
  TimeTrackingServiceTestResult,
  UpdateTimeTrackingSettingsCommand,
  VerifyTimeTrackingServiceCommand,
} from '@/features/admin-settings'

const getMock = vi.fn<() => Promise<AdminTimeTrackingSettings>>()
const updateMock =
  vi.fn<(cmd: UpdateTimeTrackingSettingsCommand) => Promise<AdminTimeTrackingSettings>>()
const testMock =
  vi.fn<(cmd: VerifyTimeTrackingServiceCommand) => Promise<TimeTrackingServiceTestResult>>()
const confirmKeyMock =
  vi.fn<(cmd: ConfirmTimeTrackingKeyCommand) => Promise<AdminTimeTrackingSettings>>()
const purgeMock = vi.fn<() => Promise<PurgeTimeTrackingCredentialsResult>>()

vi.mock('@/features/admin-settings/api/timeTrackingSettingsApi', () => ({
  getTimeTrackingSettings: () => getMock(),
  updateTimeTrackingSettings: (cmd: UpdateTimeTrackingSettingsCommand) => updateMock(cmd),
  testTimeTrackingService: (cmd: VerifyTimeTrackingServiceCommand) => testMock(cmd),
  confirmTimeTrackingKey: (cmd: ConfirmTimeTrackingKeyCommand) => confirmKeyMock(cmd),
  purgeTimeTrackingCredentials: () => purgeMock(),
}))

const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

const toastAddMock = vi.fn<(options: ToastMessageOptions) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import AdminSettingsTabTimeTracking from '../AdminSettingsTabTimeTracking.vue'

const t = i18n.global.t

const SERVICE_URL = 'http://time-tracking.example.test:3100'

function makeSettings(
  overrides: Partial<AdminTimeTrackingSettings> = {},
): AdminTimeTrackingSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    enabled: true,
    service_url: SERVICE_URL,
    api_key_configured: true,
    credential_public_key: 'public-key',
    credential_key_id: '0123456789abcdef',
    provider_label: 'Example Time',
    privacy_policy_url: null,
    is_configured: true,
    is_ready: true,
    credential_holders: [
      {
        user_id: 7,
        username: 'jane',
        full_name: 'Jane Doe',
        saved_at: '2026-09-30T08:15:00Z',
        credentials_valid: true,
        credentials_invalid_reason: null,
      },
      {
        user_id: 8,
        username: 'john',
        full_name: 'John Roe',
        saved_at: '2026-09-29T08:15:00Z',
        credentials_valid: false,
        credentials_invalid_reason: 'binding_changed',
      },
    ],
    ...overrides,
  }
}

function makeTestResult(
  overrides: Partial<TimeTrackingServiceTestResult> = {},
): TimeTrackingServiceTestResult {
  return {
    service: 'example-time-service',
    service_version: '0.1.0',
    contract_version: '0.1',
    contract_supported: true,
    credential_fields_supported: true,
    provider_label: 'Example Time',
    credential_public_key: 'new-public-key',
    credential_key_id: 'fedcba9876543210',
    key_confirmed: false,
    server_version: '1.200.0.1',
    default_project: 'DEMO',
    ...overrides,
  }
}

async function mountTab(
  settings: AdminTimeTrackingSettings,
  permissions = ['read:settings', 'write:settings'],
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    id: 1,
    is_systemuser: false,
    is_shared_account: false,
    permissions,
  } as unknown as UserResponse
  getMock.mockResolvedValue(settings)

  const wrapper = mountWithApp(AdminSettingsTabTimeTracking, { pinia })
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof mountTab>>

function button(wrapper: Wrapper, testId: string) {
  return wrapper.find<HTMLButtonElement>(`[data-testid="${testId}"]`)
}

describe('AdminSettingsTabTimeTracking', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads the settings on its own, fills the form and never shows the API key', async () => {
    const wrapper = await mountTab(makeSettings())

    expect(getMock).toHaveBeenCalledTimes(1)
    expect(wrapper.find<HTMLInputElement>('#time-tracking-service-url').element.value).toBe(
      SERVICE_URL,
    )
    const apiKey = wrapper.find<HTMLInputElement>('#time-tracking-api-key')
    expect(apiKey.element.value).toBe('')
    expect(apiKey.attributes('type')).toBe('password')
    expect(apiKey.attributes('placeholder')).toBe(t('adminSettings.timeTracking.apiKeySaved'))
    expect(wrapper.find('[data-testid="time-tracking-confirmed-key"]').text()).toContain(
      '0123456789abcdef',
    )
    expect(wrapper.find('[data-testid="time-tracking-awaiting-key"]').exists()).toBe(false)
    expect(button(wrapper, 'time-tracking-confirm-key').element.disabled).toBe(true)

    wrapper.unmount()
  })

  it('saves the fields and sends the API key only when one was typed', async () => {
    updateMock.mockResolvedValue(makeSettings())
    const wrapper = await mountTab(makeSettings({ privacy_policy_url: 'https://example.test/p' }))

    await wrapper.find('#time-tracking-privacy-url').setValue('')
    await button(wrapper, 'time-tracking-save').trigger('click')
    await flushPromises()

    expect(updateMock).toHaveBeenLastCalledWith({
      enabled: true,
      service_url: SERVICE_URL,
      privacy_policy_url: '',
    })

    await wrapper.find('#time-tracking-api-key').setValue('new-key')
    await button(wrapper, 'time-tracking-save').trigger('click')
    await flushPromises()

    expect(updateMock).toHaveBeenLastCalledWith(expect.objectContaining({ api_key: 'new-key' }))
    expect(wrapper.find<HTMLInputElement>('#time-tracking-api-key').element.value).toBe('')
    expect(useHostStore().timeTrackingEnabled).toBe(true)
    expect(useHostStore().timeTrackingProviderLabel).toBe('Example Time')

    wrapper.unmount()
  })

  it('warns while time tracking is on but no key is confirmed', async () => {
    const wrapper = await mountTab(
      makeSettings({ credential_public_key: null, credential_key_id: null, is_ready: false }),
    )

    expect(wrapper.find('[data-testid="time-tracking-awaiting-key"]').text()).toBe(
      t('adminSettings.timeTracking.awaitingKey'),
    )

    wrapper.unmount()
  })

  it('tests the unsaved service and confirms the key it serves', async () => {
    testMock.mockResolvedValue(makeTestResult())
    confirmKeyMock.mockResolvedValue(
      makeSettings({ credential_key_id: 'fedcba9876543210', credential_public_key: 'new-public-key' }),
    )
    const wrapper = await mountTab(makeSettings())

    await button(wrapper, 'time-tracking-test').trigger('click')
    await flushPromises()

    expect(testMock).toHaveBeenCalledWith({ service_url: SERVICE_URL })
    expect(wrapper.find('[data-testid="time-tracking-test-result"]').text()).toContain(
      'fedcba9876543210',
    )

    await button(wrapper, 'time-tracking-confirm-key').trigger('click')
    await flushPromises()

    expect(confirmKeyMock).toHaveBeenCalledWith({ credential_key_id: 'fedcba9876543210' })
    expect(wrapper.find('[data-testid="time-tracking-key-is-confirmed"]').exists()).toBe(true)
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'success',
        summary: t('adminSettings.timeTracking.keyConfirmed'),
      }),
    )

    wrapper.unmount()
  })

  it('only confirms a key once the form is saved', async () => {
    testMock.mockResolvedValue(makeTestResult())
    const wrapper = await mountTab(makeSettings())

    await wrapper.find('#time-tracking-service-url').setValue('http://other.example.test')
    await button(wrapper, 'time-tracking-test').trigger('click')
    await flushPromises()

    expect(button(wrapper, 'time-tracking-confirm-key').element.disabled).toBe(true)

    wrapper.unmount()
  })

  it('warns about an unsupported contract and unsupported credential fields', async () => {
    testMock.mockResolvedValue(
      makeTestResult({ contract_supported: false, credential_fields_supported: false }),
    )
    const wrapper = await mountTab(makeSettings())

    await button(wrapper, 'time-tracking-test').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="time-tracking-contract-unsupported"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="time-tracking-fields-unsupported"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('shows a translated message when the service cannot be reached', async () => {
    testMock.mockRejectedValue({
      isAxiosError: true,
      response: { status: 503, data: { detail: 'x', code: 'TimeTrackingUnavailableError' } },
    })
    const wrapper = await mountTab(makeSettings())

    await button(wrapper, 'time-tracking-test').trigger('click')
    await flushPromises()

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        summary: t('adminSettings.timeTracking.testFailed'),
        detail: t('timeTracking.errors.unavailable'),
      }),
    )

    wrapper.unmount()
  })

  it('lists who stored credentials and purges them only after confirmation', async () => {
    purgeMock.mockResolvedValue({ deleted: 2 })
    const wrapper = await mountTab(makeSettings())

    const table = wrapper.find('[data-testid="time-tracking-holders"]')
    expect(table.text()).toContain('jane')
    expect(table.text()).toContain('John Roe')
    expect(table.text()).toContain(t('adminSettings.timeTracking.reasons.binding_changed'))

    await button(wrapper, 'time-tracking-purge').trigger('click')
    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    expect(purgeMock).not.toHaveBeenCalled()

    await (confirmRequireMock.mock.calls[0]![0].accept as () => Promise<void>)()
    await flushPromises()

    expect(purgeMock).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="time-tracking-holders"]').text()).toContain(
      t('adminSettings.timeTracking.noHolders'),
    )
    expect(button(wrapper, 'time-tracking-purge').element.disabled).toBe(true)

    wrapper.unmount()
  })

  it('is read-only without write:settings', async () => {
    const wrapper = await mountTab(makeSettings(), ['read:settings'])

    expect(button(wrapper, 'time-tracking-save').element.disabled).toBe(true)
    expect(button(wrapper, 'time-tracking-test').element.disabled).toBe(true)
    expect(button(wrapper, 'time-tracking-purge').element.disabled).toBe(true)

    wrapper.unmount()
  })
})
