import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ToastMessageOptions } from 'openvue/toast'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { setDisplayTimezone } from '@/core/utils/dates'
import { i18n } from '@/core/i18n'
import type { UserResponse } from '@/core/types/userResponse'
import type {
  SaveTimeTrackingCredentialsRequest,
  TimeTrackingAccountResponse,
  TimeTrackingDay,
  TimeTrackingMonthResponse,
  TimeTrackingYearResponse,
} from '../../types/timeTrackingTypes'

const getAccountMock = vi.fn<() => Promise<TimeTrackingAccountResponse>>()
const saveAccountMock =
  vi.fn<(body: SaveTimeTrackingCredentialsRequest) => Promise<TimeTrackingAccountResponse>>()
const getMonthMock = vi.fn<(month: string) => Promise<TimeTrackingMonthResponse>>()
const getYearMock = vi.fn<(year: number) => Promise<TimeTrackingYearResponse>>()

vi.mock('../../api/timeTrackingApi', () => ({
  getMyTimeTrackingAccount: () => getAccountMock(),
  saveMyTimeTrackingAccount: (body: SaveTimeTrackingCredentialsRequest) => saveAccountMock(body),
  deleteMyTimeTrackingAccount: vi.fn<() => Promise<void>>(),
  checkMyTimeTrackingAccess: vi.fn<() => Promise<TimeTrackingAccountResponse>>(),
  getMyTimeTrackingMonth: (month: string) => getMonthMock(month),
  getMyTimeTrackingYear: (year: number) => getYearMock(year),
}))

const toastAddMock = vi.fn<(options: ToastMessageOptions) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import AccountTimeTrackingView from '../AccountTimeTrackingView.vue'
import TimeTrackingConsentDialog from '../../components/TimeTrackingConsentDialog.vue'
import { resetTimeTrackingFetchSpacing } from '../../composables/useTimeTrackingData'

const t = i18n.global.t

const NOW = new Date('2026-10-06T08:30:20Z')

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

function makeDay(date: string, overrides: Partial<TimeTrackingDay> = {}): TimeTrackingDay {
  return {
    date,
    weekday: new Date(`${date}T00:00:00Z`).getUTCDay() || 7,
    shift_name: 'Full time 38.5h',
    shift_short_name: 'FT',
    first_in: `${date}T06:00:00Z`,
    last_out: `${date}T14:00:00Z`,
    bookings: [
      { at: `${date}T06:00:00Z`, direction: 'in' },
      { at: `${date}T14:00:00Z`, direction: 'out' },
    ],
    worked_seconds: 8 * 3600,
    target_seconds: 7.7 * 3600,
    day_balance_seconds: 0.3 * 3600,
    running_balance_seconds: 3600,
    status: 'normal',
    ...overrides,
  }
}

function makeMonth(month: string, overrides: Partial<TimeTrackingMonthResponse> = {}): TimeTrackingMonthResponse {
  return {
    month,
    first_day: `${month}-01`,
    last_day: `${month}-31`,
    employee_name: 'Doe, Jane',
    days: [makeDay(`${month}-01`), makeDay(`${month}-02`)],
    accounts: [
      { account_id: 1, name: 'Overtime', short_name: 'OT', format: 'duration_clock', pre: 3600, sum: 1800, post: 5400 },
      { account_id: 2, name: 'Unused', short_name: 'UN', format: 'count', pre: 0, sum: 0, post: 0 },
    ],
    totals: {
      today: null,
      worked_seconds: 16 * 3600,
      target_seconds: 15.4 * 3600,
      balance_seconds: 0.6 * 3600,
    },
    rights: { days: null, month: true, year: null },
    fetched_at: NOW.toISOString(),
    ...overrides,
  }
}

function currentMonthWithClockIn(): TimeTrackingMonthResponse {
  const today = makeDay('2026-10-06', {
    last_out: null,
    bookings: [{ at: '2026-10-06T06:00:00Z', direction: 'in' }],
    worked_seconds: 2 * 3600 + 30 * 60,
    day_balance_seconds: -(5.2 * 3600),
    running_balance_seconds: null,
    status: 'open',
  })
  return makeMonth('2026-10', {
    days: [makeDay('2026-10-05'), today],
    totals: {
      today: {
        date: '2026-10-06',
        worked_seconds: 2 * 3600 + 30 * 60,
        target_seconds: 8 * 3600,
        day_balance_seconds: -(5 * 3600 + 30 * 60),
        running_balance_seconds: -(4 * 3600 + 30 * 60),
        clocked_in: true,
        first_in: '2026-10-06T06:00:00Z',
        target_reached_at: '2026-10-06T14:00:00Z',
      },
      worked_seconds: 10 * 3600 + 30 * 60,
      target_seconds: 15.7 * 3600,
      balance_seconds: -(5.2 * 3600),
    },
  })
}

function apiError(code: string, status = 400) {
  return { isAxiosError: true, response: { status, data: { detail: 'English detail', code } } }
}

async function mountView(account: TimeTrackingAccountResponse = makeAccount()) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const hostStore = useHostStore()
  hostStore.timeTrackingEnabled = true
  hostStore.timeTrackingProviderLabel = 'Example Time'
  hostStore.loaded = true
  useCurrentUserStore().user = {
    id: 7,
    is_systemuser: false,
    is_shared_account: false,
    permissions: [],
  } as unknown as UserResponse
  getAccountMock.mockResolvedValue(account)

  const wrapper = mountWithApp(AccountTimeTrackingView, {
    pinia,
    attachTo: document.body,
    global: { stubs: { RouterLink: RouterLinkStub, Chart: true } },
  })
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof mountView>>

function button(wrapper: Wrapper, testId: string) {
  return wrapper.find<HTMLButtonElement>(`[data-testid="${testId}"]`)
}

describe('AccountTimeTrackingView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
    vi.setSystemTime(NOW)
    setDisplayTimezone('UTC')
    resetTimeTrackingFetchSpacing()
    getMonthMock.mockImplementation((month) => Promise.resolve(makeMonth(month)))
    getYearMock.mockResolvedValue({
      year: 2026,
      employee_name: 'Doe, Jane',
      months: [{ month: 9, worked_seconds: 3600, target_seconds: 3600, balance_seconds: 0, end_balance_seconds: 0 }],
      end_balance_seconds: 0,
      rights: { days: null, month: null, year: true },
      fetched_at: NOW.toISOString(),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    setDisplayTimezone(null)
    document.body.innerHTML = ''
  })

  it('fetches the current month once on mount', async () => {
    const wrapper = await mountView()

    expect(getAccountMock).toHaveBeenCalledTimes(1)
    expect(getMonthMock).toHaveBeenCalledTimes(1)
    expect(getMonthMock).toHaveBeenCalledWith('2026-10')
    expect(getYearMock).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="time-tracking-month-table"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Doe, Jane')

    wrapper.unmount()
  })

  it('shows an empty state linking to My Account and fetches nothing without credentials', async () => {
    const wrapper = await mountView(
      makeAccount({
        time_tracking_user: null,
        time_tracking_password_configured: false,
        time_tracking_credentials_valid: false,
        time_tracking_credentials_invalid_reason: 'missing',
        time_tracking_consent_current: false,
      }),
    )

    expect(getMonthMock).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="time-tracking-empty"]').text()).toContain(
      t('timeTracking.empty.missing', { provider: 'Example Time' }),
    )
    expect(wrapper.findComponent(RouterLinkStub).props('to')).toBe('/account/me')
    expect(button(wrapper, 'time-tracking-reload').element.disabled).toBe(true)

    wrapper.unmount()
  })

  it('refetches the shown month on reload, after a short cooldown', async () => {
    const wrapper = await mountView()
    expect(getMonthMock).toHaveBeenCalledTimes(1)

    expect(button(wrapper, 'time-tracking-reload').element.disabled).toBe(true)

    await vi.advanceTimersByTimeAsync(5_000)
    await flushPromises()
    expect(button(wrapper, 'time-tracking-reload').element.disabled).toBe(false)

    await button(wrapper, 'time-tracking-reload').trigger('click')
    await flushPromises()

    expect(getMonthMock).toHaveBeenCalledTimes(2)
    expect(getMonthMock).toHaveBeenLastCalledWith('2026-10')
    expect(button(wrapper, 'time-tracking-reload').element.disabled).toBe(true)

    wrapper.unmount()
  })

  it('switches months without allowing future ones', async () => {
    const wrapper = await mountView()

    expect(button(wrapper, 'time-tracking-next-month').element.disabled).toBe(true)
    expect(button(wrapper, 'time-tracking-current-month').element.disabled).toBe(true)

    await button(wrapper, 'time-tracking-previous-month').trigger('click')
    // A switch right after the first load waits out the server's spacing.
    expect(getMonthMock).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(5_000)
    await flushPromises()

    expect(getMonthMock).toHaveBeenCalledTimes(2)
    expect(getMonthMock).toHaveBeenLastCalledWith('2026-09')
    expect(button(wrapper, 'time-tracking-next-month').element.disabled).toBe(false)

    await vi.advanceTimersByTimeAsync(5_000)
    await button(wrapper, 'time-tracking-current-month').trigger('click')
    await flushPromises()

    expect(getMonthMock).toHaveBeenLastCalledWith('2026-10')
    expect(button(wrapper, 'time-tracking-next-month').element.disabled).toBe(true)

    wrapper.unmount()
  })

  it('sends only the latest month when switching several times quickly', async () => {
    const wrapper = await mountView()

    await button(wrapper, 'time-tracking-previous-month').trigger('click')
    await button(wrapper, 'time-tracking-previous-month').trigger('click')
    await button(wrapper, 'time-tracking-previous-month').trigger('click')
    await vi.advanceTimersByTimeAsync(5_000)
    await flushPromises()

    expect(getMonthMock).toHaveBeenCalledTimes(2)
    expect(getMonthMock).toHaveBeenLastCalledWith('2026-07')

    wrapper.unmount()
  })

  it('loads the year only when its section is opened', async () => {
    const wrapper = await mountView()
    expect(getYearMock).not.toHaveBeenCalled()

    await wrapper.find('[data-testid="time-tracking-year"] button').trigger('click')
    await flushPromises()

    expect(getYearMock).toHaveBeenCalledWith(2026)
    expect(wrapper.find('[data-testid="time-tracking-year-chart"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('always lists every account, including those at zero, inside a scroll area', async () => {
    const wrapper = await mountView()

    const scroll = wrapper.find('[data-testid="time-tracking-accounts-scroll"]')
    expect(scroll.exists()).toBe(true)
    expect(scroll.findAll('[data-testid="time-tracking-account-row"]')).toHaveLength(2)
    expect(wrapper.find('[data-testid="time-tracking-accounts-show-all"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('keeps today ticking every minute while clocked in, without refetching', async () => {
    getMonthMock.mockResolvedValue(currentMonthWithClockIn())
    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="time-tracking-worked-today"]').text()).toBe('2:30')
    expect(wrapper.find('[data-testid="time-tracking-day-balance"]').text()).toBe('-5:30')

    // 08:30:20 to 08:31:00 crosses one minute boundary.
    await vi.advanceTimersByTimeAsync(40_000)
    expect(wrapper.find('[data-testid="time-tracking-worked-today"]').text()).toBe('2:31')
    expect(wrapper.find('[data-testid="time-tracking-day-balance"]').text()).toBe('-5:29')

    await vi.advanceTimersByTimeAsync(60_000)
    expect(wrapper.find('[data-testid="time-tracking-worked-today"]').text()).toBe('2:32')
    expect(getMonthMock).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('asks for consent first when the consent text changed, then loads the month', async () => {
    saveAccountMock.mockResolvedValue(makeAccount())
    const wrapper = await mountView(
      makeAccount({
        time_tracking_credentials_valid: false,
        time_tracking_credentials_invalid_reason: 'consent_outdated',
        time_tracking_consent_current: false,
        time_tracking_consent_version: 2,
      }),
    )

    const dialog = wrapper.findComponent(TimeTrackingConsentDialog)
    expect(dialog.props('visible')).toBe(true)
    expect(getMonthMock).not.toHaveBeenCalled()

    dialog.vm.$emit('confirm')
    await flushPromises()

    expect(saveAccountMock).toHaveBeenCalledWith({
      time_tracking_user: 'jdoe',
      time_tracking_consent_version: 2,
    })
    expect(getMonthMock).toHaveBeenCalledWith('2026-10')

    wrapper.unmount()
  })

  it('re-reads the account and stops when the stored credentials are rejected', async () => {
    getMonthMock.mockRejectedValue(apiError('TimeTrackingAuthenticationFailedError'))
    getAccountMock.mockResolvedValueOnce(makeAccount()).mockResolvedValueOnce(
      makeAccount({
        time_tracking_credentials_valid: false,
        time_tracking_credentials_invalid_reason: 'auth_failed',
      }),
    )
    const pinia = createPinia()
    setActivePinia(pinia)
    const hostStore = useHostStore()
    hostStore.timeTrackingEnabled = true
    hostStore.timeTrackingProviderLabel = 'Example Time'
    useCurrentUserStore().user = { id: 7, is_systemuser: false, is_shared_account: false } as UserResponse
    const wrapper = mountWithApp(AccountTimeTrackingView, {
      pinia,
      global: { stubs: { RouterLink: RouterLinkStub, Chart: true } },
    })
    await flushPromises()

    expect(getAccountMock).toHaveBeenCalledTimes(2)
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        detail: t('timeTracking.errors.authenticationFailed'),
      }),
    )
    expect(wrapper.find('[data-testid="time-tracking-empty"]').text()).toContain(
      t('timeTracking.empty.auth_failed', { provider: 'Example Time' }),
    )

    wrapper.unmount()
  })
})
