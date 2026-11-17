import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { TimeTrackingAccountResponse } from '../../types/timeTrackingTypes'

const getAccountMock = vi.fn<() => Promise<TimeTrackingAccountResponse>>()

vi.mock('../../api/timeTrackingApi', () => ({
  getMyTimeTrackingAccount: () => getAccountMock(),
}))

import { useTimeTrackingAccountStore } from '../timeTrackingAccountStore'

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

describe('timeTrackingAccountStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getAccountMock.mockResolvedValue(makeAccount())
  })

  it('loads once for concurrent and later callers', async () => {
    const store = useTimeTrackingAccountStore()

    await Promise.all([store.ensureLoaded(), store.ensureLoaded()])
    await store.ensureLoaded()

    expect(getAccountMock).toHaveBeenCalledTimes(1)
    expect(store.loaded).toBe(true)
    expect(store.credentialsValid).toBe(true)
  })

  it('stays retryable after a failed load', async () => {
    getAccountMock.mockRejectedValueOnce(new Error('network'))
    const store = useTimeTrackingAccountStore()

    await store.ensureLoaded()
    expect(store.loaded).toBe(false)

    await store.ensureLoaded()
    expect(store.loaded).toBe(true)
    expect(getAccountMock).toHaveBeenCalledTimes(2)
  })

  it('never keeps the verification result of a save or check', () => {
    const store = useTimeTrackingAccountStore()

    store.setAccount(
      makeAccount({
        time_tracking_employee_name: 'Doe, Jane',
        time_tracking_rights: { days: true, month: true, year: false },
      }),
    )

    expect(store.account?.time_tracking_employee_name).toBeNull()
    expect(store.account?.time_tracking_rights).toBeNull()
    expect(store.account?.time_tracking_user).toBe('jdoe')
  })
})
