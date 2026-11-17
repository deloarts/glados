import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ToastMessageOptions } from 'openvue/toast'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'
import type { UserResponse } from '@/core/types/userResponse'
import type {
  SaveTimeTrackingCredentialsRequest,
  TimeTrackingAccountResponse,
} from '@/features/time-tracking'

const updateCurrentUserMock = vi.fn<(payload: unknown) => Promise<UserResponse>>()
vi.mock('../../api/updateCurrentUser', () => ({
  updateCurrentUser: (payload: unknown) => updateCurrentUserMock(payload),
}))

const getAccountMock = vi.fn<() => Promise<TimeTrackingAccountResponse>>()
const saveAccountMock =
  vi.fn<(body: SaveTimeTrackingCredentialsRequest) => Promise<TimeTrackingAccountResponse>>()
const getMonthMock = vi.fn<(month: string) => Promise<unknown>>()

vi.mock('@/features/time-tracking/api/timeTrackingApi', () => ({
  getMyTimeTrackingAccount: () => getAccountMock(),
  saveMyTimeTrackingAccount: (body: SaveTimeTrackingCredentialsRequest) => saveAccountMock(body),
  deleteMyTimeTrackingAccount: vi.fn<() => Promise<void>>(),
  checkMyTimeTrackingAccess: vi.fn<() => Promise<TimeTrackingAccountResponse>>(),
  getMyTimeTrackingMonth: (month: string) => getMonthMock(month),
  getMyTimeTrackingYear: vi.fn<() => Promise<unknown>>(),
}))

const toastAddMock = vi.fn<(options: ToastMessageOptions) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import AccountMeView from '../AccountMeView.vue'

const t = i18n.global.t

function makeAccount(overrides: Partial<TimeTrackingAccountResponse> = {}): TimeTrackingAccountResponse {
  return {
    time_tracking_user: 'jdoe',
    time_tracking_password_configured: true,
    time_tracking_credentials_valid: true,
    time_tracking_credentials_invalid_reason: null,
    time_tracking_consent_version: 1,
    time_tracking_consent_current: true,
    time_tracking_privacy_policy_url: null,
    time_tracking_provider_label: 'Example Time',
    time_tracking_employee_name: null,
    time_tracking_rights: null,
    ...overrides,
  }
}

async function mountPage(options: { enabled: boolean; user?: UserResponse }) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = options.user ?? makeUserResponse()
  const hostStore = useHostStore()
  hostStore.timeTrackingEnabled = options.enabled
  hostStore.timeTrackingProviderLabel = options.enabled ? 'Example Time' : null

  const wrapper = mountWithApp(AccountMeView, {
    pinia,
    global: { plugins: [ConfirmationService] },
  })
  await flushPromises()
  return wrapper
}

function saveButton(wrapper: Awaited<ReturnType<typeof mountPage>>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (t('common.save') as string))!
}

describe('AccountMeView, time tracking section', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    updateCurrentUserMock.mockResolvedValue(makeUserResponse())
    getAccountMock.mockResolvedValue(makeAccount())
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('is not shown, and nothing is requested, while time tracking is off', async () => {
    const wrapper = await mountPage({ enabled: false })

    expect(wrapper.find('[data-testid="account-time-tracking-section"]').exists()).toBe(false)
    expect(getAccountMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('is not shown for a shared account', async () => {
    const wrapper = await mountPage({
      enabled: true,
      user: makeUserResponse({ is_shared_account: true }),
    })

    expect(wrapper.find('[data-testid="account-time-tracking-section"]').exists()).toBe(false)
    expect(getAccountMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('sits between the start page and the theme preset, reading only the account state', async () => {
    const wrapper = await mountPage({ enabled: true })

    const html = wrapper.html()
    const startPage = html.indexOf(t('accountMe.regional.startPage'))
    const section = html.indexOf('data-testid="account-time-tracking-section"')
    const preset = html.indexOf(t('accountMe.theme.preset'))
    expect(startPage).toBeGreaterThan(-1)
    expect(section).toBeGreaterThan(startPage)
    expect(preset).toBeGreaterThan(section)
    expect(getAccountMock).toHaveBeenCalledTimes(1)
    expect(getMonthMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('leaves the credentials alone when Save is pressed without changes to them', async () => {
    const wrapper = await mountPage({ enabled: true })

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(updateCurrentUserMock).toHaveBeenCalledTimes(1)
    expect(saveAccountMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('saves changed credentials with the page Save, and the profile even when they are refused', async () => {
    saveAccountMock.mockRejectedValue({
      isAxiosError: true,
      response: { status: 400, data: { detail: 'x', code: 'TimeTrackingAuthenticationFailedError' } },
    })
    const wrapper = await mountPage({ enabled: true })

    await wrapper.find('#account-time-tracking-password').setValue('wrong')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(saveAccountMock).toHaveBeenCalledTimes(1)
    expect(updateCurrentUserMock).toHaveBeenCalledTimes(1)
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'success', summary: t('accountMe.saved') }),
    )
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        summary: t('accountMe.timeTracking.saveFailed', { provider: 'Example Time' }),
      }),
    )
    expect(wrapper.find<HTMLInputElement>('#account-time-tracking-password').element.value).toBe('')

    wrapper.unmount()
  })
})
