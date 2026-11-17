import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'
import type { ToastMessageOptions } from 'openvue/toast'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'
import type {
  SaveTimeTrackingCredentialsRequest,
  TimeTrackingAccountResponse,
} from '@/features/time-tracking'

const getAccountMock = vi.fn<() => Promise<TimeTrackingAccountResponse>>()
const saveAccountMock =
  vi.fn<(body: SaveTimeTrackingCredentialsRequest) => Promise<TimeTrackingAccountResponse>>()
const deleteAccountMock = vi.fn<() => Promise<void>>()
const checkAccessMock = vi.fn<() => Promise<TimeTrackingAccountResponse>>()
const getMonthMock = vi.fn<(month: string) => Promise<unknown>>()
const getYearMock = vi.fn<(year: number) => Promise<unknown>>()

vi.mock('@/features/time-tracking/api/timeTrackingApi', () => ({
  getMyTimeTrackingAccount: () => getAccountMock(),
  saveMyTimeTrackingAccount: (body: SaveTimeTrackingCredentialsRequest) => saveAccountMock(body),
  deleteMyTimeTrackingAccount: () => deleteAccountMock(),
  checkMyTimeTrackingAccess: () => checkAccessMock(),
  getMyTimeTrackingMonth: (month: string) => getMonthMock(month),
  getMyTimeTrackingYear: (year: number) => getYearMock(year),
}))

const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

const toastAddMock = vi.fn<(options: ToastMessageOptions) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import AccountTimeTrackingSection from '../AccountTimeTrackingSection.vue'
import { TimeTrackingConsentDialog } from '@/features/time-tracking'

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

function apiError(code: string, status = 400) {
  return { isAxiosError: true, response: { status, data: { detail: 'English detail', code } } }
}

type SectionVm = { isDirty: boolean; save: () => Promise<void> }

async function mountSection(account: TimeTrackingAccountResponse) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const hostStore = useHostStore()
  hostStore.timeTrackingEnabled = true
  hostStore.timeTrackingProviderLabel = 'Example Time'
  getAccountMock.mockResolvedValue(account)

  const wrapper = mountWithApp(AccountTimeTrackingSection, { pinia })
  await flushPromises()
  return wrapper
}

function input(wrapper: Awaited<ReturnType<typeof mountSection>>, id: string) {
  return wrapper.find<HTMLInputElement>(`#${id}`)
}

describe('AccountTimeTrackingSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('reads only the stored account on open, never the time tracking data', async () => {
    const wrapper = await mountSection(makeAccount())

    expect(getAccountMock).toHaveBeenCalledTimes(1)
    expect(checkAccessMock).not.toHaveBeenCalled()
    expect(saveAccountMock).not.toHaveBeenCalled()
    expect(getMonthMock).not.toHaveBeenCalled()
    expect(getYearMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('labels the fields with the provider name and prefills the user name', async () => {
    const wrapper = await mountSection(makeAccount())

    expect(wrapper.text()).toContain(t('accountMe.timeTracking.user', { provider: 'Example Time' }))
    expect(wrapper.text()).toContain(t('accountMe.timeTracking.password', { provider: 'Example Time' }))
    expect(input(wrapper, 'account-time-tracking-user').element.value).toBe('jdoe')
    expect(input(wrapper, 'account-time-tracking-password').element.value).toBe('')

    wrapper.unmount()
  })

  it('keeps the browser from autofilling or saving the password', async () => {
    const wrapper = await mountSection(makeAccount())

    expect(input(wrapper, 'account-time-tracking-password').attributes('autocomplete')).toBe(
      'new-password',
    )
    expect(input(wrapper, 'account-time-tracking-password').attributes('type')).toBe('password')
    expect(input(wrapper, 'account-time-tracking-user').attributes('autocomplete')).toBe('off')

    wrapper.unmount()
  })

  it('asks only for user name and password, never for a project', async () => {
    const wrapper = await mountSection(makeAccount())

    expect(wrapper.find('#account-time-tracking-project').exists()).toBe(false)
    expect(wrapper.find('[data-testid="time-tracking-insecure-notice"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('requires the password again when the user name changes', async () => {
    const wrapper = await mountSection(makeAccount())

    await input(wrapper, 'account-time-tracking-user').setValue('another.user')
    await (wrapper.vm as unknown as SectionVm).save()
    await flushPromises()

    expect(saveAccountMock).not.toHaveBeenCalled()
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'warn',
        summary: t('accountMe.timeTracking.errors.passwordRequired', { provider: 'Example Time' }),
      }),
    )

    wrapper.unmount()
  })

  it.each(['binding_changed', 'auth_failed', 'undecryptable', 'consent_outdated'] as const)(
    'asks to enter the credentials again for reason %s',
    async (reason) => {
      const wrapper = await mountSection(
        makeAccount({
          time_tracking_credentials_valid: false,
          time_tracking_credentials_invalid_reason: reason,
        }),
      )

      expect(wrapper.find('[data-testid="time-tracking-invalid-hint"]').text()).toBe(
        t(`accountMe.timeTracking.invalid.${reason}`, { provider: 'Example Time' }),
      )

      wrapper.unmount()
    },
  )

  it('opens the consent dialog before the first save and sends nothing until confirmed', async () => {
    const account = makeAccount({
      time_tracking_user: null,
      time_tracking_password_configured: false,
      time_tracking_credentials_valid: false,
      time_tracking_credentials_invalid_reason: 'missing',
      time_tracking_consent_current: false,
    })
    saveAccountMock.mockResolvedValue(
      makeAccount({
        time_tracking_employee_name: 'Doe, Jane',
        time_tracking_rights: { days: false, month: true, year: true },
      }),
    )
    const wrapper = await mountSection(account)

    await input(wrapper, 'account-time-tracking-user').setValue('jdoe')
    await input(wrapper, 'account-time-tracking-password').setValue('s3cret')
    const vm = wrapper.vm as unknown as SectionVm
    expect(vm.isDirty).toBe(true)

    const saving = vm.save()
    await flushPromises()

    const dialog = wrapper.findComponent(TimeTrackingConsentDialog)
    expect(dialog.props('visible')).toBe(true)
    expect(saveAccountMock).not.toHaveBeenCalled()

    dialog.vm.$emit('confirm')
    await saving
    await flushPromises()

    expect(saveAccountMock).toHaveBeenCalledWith({
      time_tracking_user: 'jdoe',
      time_tracking_password: 's3cret',
      time_tracking_consent_version: 1,
    })
    expect(input(wrapper, 'account-time-tracking-password').element.value).toBe('')
    expect(wrapper.find('[data-testid="time-tracking-verification"]').text()).toContain(
      t('accountMe.timeTracking.signedInAs', { name: 'Doe, Jane' }),
    )
    expect(
      wrapper.find('[data-testid="time-tracking-right-days"]').attributes('data-allowed'),
    ).toBe('false')
    expect(
      wrapper.find('[data-testid="time-tracking-right-month"]').attributes('data-allowed'),
    ).toBe('true')

    wrapper.unmount()
  })

  it('does not save when the consent is declined', async () => {
    const wrapper = await mountSection(makeAccount({ time_tracking_consent_current: false }))

    await input(wrapper, 'account-time-tracking-password').setValue('s3cret')
    const saving = (wrapper.vm as unknown as SectionVm).save()
    await flushPromises()
    wrapper.findComponent(TimeTrackingConsentDialog).vm.$emit('cancel')
    await saving

    expect(saveAccountMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('saves straight away while the stored consent is current, keeping the stored password', async () => {
    saveAccountMock.mockResolvedValue(makeAccount())
    const wrapper = await mountSection(makeAccount())

    await (wrapper.vm as unknown as SectionVm).save()
    await flushPromises()

    expect(wrapper.findComponent(TimeTrackingConsentDialog).props('visible')).toBe(false)
    expect(saveAccountMock).toHaveBeenCalledWith({
      time_tracking_user: 'jdoe',
      time_tracking_password: null,
      time_tracking_consent_version: 1,
    })

    wrapper.unmount()
  })

  it('clears the password and shows a translated toast when the sign-in is refused', async () => {
    saveAccountMock.mockRejectedValue(apiError('TimeTrackingAuthenticationFailedError'))
    const wrapper = await mountSection(makeAccount())

    await input(wrapper, 'account-time-tracking-password').setValue('wrong')
    await (wrapper.vm as unknown as SectionVm).save()
    await flushPromises()

    expect(input(wrapper, 'account-time-tracking-password').element.value).toBe('')
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        summary: t('accountMe.timeTracking.saveFailed', { provider: 'Example Time' }),
        detail: t('timeTracking.errors.authenticationFailed'),
      }),
    )

    wrapper.unmount()
  })

  it('confirms a changed consent text without asking for the password again', async () => {
    saveAccountMock.mockResolvedValue(makeAccount())
    const wrapper = await mountSection(
      makeAccount({
        time_tracking_credentials_valid: false,
        time_tracking_credentials_invalid_reason: 'consent_outdated',
        time_tracking_consent_current: false,
        time_tracking_consent_version: 2,
      }),
    )

    await wrapper.find('[data-testid="time-tracking-confirm-consent"]').trigger('click')
    await flushPromises()
    const dialog = wrapper.findComponent(TimeTrackingConsentDialog)
    expect(dialog.props('visible')).toBe(true)

    dialog.vm.$emit('confirm')
    await flushPromises()

    expect(saveAccountMock).toHaveBeenCalledWith({
      time_tracking_user: 'jdoe',
      time_tracking_password: null,
      time_tracking_consent_version: 2,
    })

    wrapper.unmount()
  })

  it('requires the password again when the server or key changed', async () => {
    const wrapper = await mountSection(
      makeAccount({
        time_tracking_credentials_valid: false,
        time_tracking_credentials_invalid_reason: 'binding_changed',
      }),
    )

    await (wrapper.vm as unknown as SectionVm).save()
    await flushPromises()

    expect(saveAccountMock).not.toHaveBeenCalled()
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'warn',
        summary: t('accountMe.timeTracking.errors.passwordRequired', { provider: 'Example Time' }),
      }),
    )

    wrapper.unmount()
  })

  it('shows the read rights only after an explicit access check', async () => {
    checkAccessMock.mockResolvedValue(
      makeAccount({
        time_tracking_employee_name: 'Doe, Jane',
        time_tracking_rights: { days: true, month: true, year: false },
      }),
    )
    const wrapper = await mountSection(makeAccount())

    expect(wrapper.find('[data-testid="time-tracking-verification"]').exists()).toBe(false)

    await wrapper.find('[data-testid="time-tracking-check-access"]').trigger('click')
    await flushPromises()

    expect(checkAccessMock).toHaveBeenCalledTimes(1)
    expect(
      wrapper.find('[data-testid="time-tracking-right-year"]').attributes('data-allowed'),
    ).toBe('false')

    wrapper.unmount()
  })

  it('removes the credentials after confirmation and reloads the account state', async () => {
    deleteAccountMock.mockResolvedValue()
    const wrapper = await mountSection(makeAccount())
    getAccountMock.mockResolvedValue(
      makeAccount({
        time_tracking_user: null,
        time_tracking_password_configured: false,
        time_tracking_credentials_valid: false,
        time_tracking_credentials_invalid_reason: 'missing',
        time_tracking_consent_current: false,
      }),
    )

    await wrapper.find('[data-testid="time-tracking-remove"]').trigger('click')
    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    expect(deleteAccountMock).not.toHaveBeenCalled()

    await (confirmRequireMock.mock.calls[0]![0].accept as () => Promise<void>)()
    await flushPromises()

    expect(deleteAccountMock).toHaveBeenCalledTimes(1)
    expect(getAccountMock).toHaveBeenCalledTimes(2)
    expect(input(wrapper, 'account-time-tracking-user').element.value).toBe('')
    expect(wrapper.find('[data-testid="time-tracking-remove"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('explains in a tooltip why Check access is off', async () => {
    function checkTooltip(wrapper: Awaited<ReturnType<typeof mountSection>>): string | undefined {
      const span = wrapper.find('[data-testid="time-tracking-check-access-tooltip"]')
      return (span.element as HTMLElement & { $_ptooltipValue?: string }).$_ptooltipValue
    }

    // The directive unbinds an emptied tooltip but keeps its last text, so
    // the usable case is read from the button.
    const valid = await mountSection(makeAccount())
    const check = valid.find<HTMLButtonElement>('[data-testid="time-tracking-check-access"]')
    expect(check.element.disabled).toBe(false)
    await input(valid, 'account-time-tracking-user').setValue('someone-else')
    expect(checkTooltip(valid)).toBe(t('accountMe.timeTracking.checkBlocked.unsaved'))
    valid.unmount()

    const missing = await mountSection(
      makeAccount({
        time_tracking_user: null,
        time_tracking_password_configured: false,
        time_tracking_credentials_valid: false,
        time_tracking_credentials_invalid_reason: 'missing',
      }),
    )
    expect(checkTooltip(missing)).toBe(t('accountMe.timeTracking.checkBlocked.missing'))
    missing.unmount()

    const rejected = await mountSection(
      makeAccount({
        time_tracking_credentials_valid: false,
        time_tracking_credentials_invalid_reason: 'auth_failed',
      }),
    )
    expect(checkTooltip(rejected)).toBe(t('accountMe.timeTracking.checkBlocked.password'))
    rejected.unmount()
  })
})
