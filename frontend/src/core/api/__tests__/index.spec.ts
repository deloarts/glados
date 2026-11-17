import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// This spec exercises the real axios instance (module-eval `axios.create()`
// is harmless on its own, since it makes no request), invoking its response
// interceptor's `rejected` handler directly rather than mocking the network.
// Only the two stores the interceptor talks to are mocked.
const reportSuccessMock = vi.fn<() => void>()
const reportFailureMock = vi.fn<() => void>()

vi.mock('@/core/stores/connectionStore', () => ({
  useConnectionStore: () => ({
    reportSuccess: reportSuccessMock,
    reportFailure: reportFailureMock,
  }),
}))

const sessionExpiredMock = vi.fn<() => void>()
const maintenanceLockoutMock = vi.fn<() => void>()

// Lazily imported inside the interceptor on purpose (see index.ts's own
// comment on why); vi.mock hoists regardless of the import being dynamic.
vi.mock('@/core/stores/currentUserStore', () => ({
  useCurrentUserStore: () => ({
    sessionExpired: sessionExpiredMock,
    maintenanceLockout: maintenanceLockoutMock,
  }),
}))

import api from '../index'

// axios's InterceptorManager keeps registered interceptors in this array;
// index.ts registers exactly one response interceptor, so its `rejected`
// handler is what a rejected request actually reaches.
function rejectedHandler() {
  const handlers = (
    api.interceptors.response as unknown as {
      handlers: { rejected: (error: unknown) => Promise<never> }[]
    }
  ).handlers
  return handlers[0]!.rejected
}

describe('api response interceptor, maintenance mode', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('still routes a 401 to sessionExpired(), unaffected by the new branch', async () => {
    const error = { isAxiosError: true, response: { status: 401, data: {} } }

    await expect(rejectedHandler()(error)).rejects.toBe(error)

    expect(sessionExpiredMock).toHaveBeenCalledOnce()
    expect(maintenanceLockoutMock).not.toHaveBeenCalled()
  })

  it('routes a 503 MaintenanceModeError to maintenanceLockout()', async () => {
    const error = {
      isAxiosError: true,
      response: { status: 503, data: { code: 'MaintenanceModeError' } },
    }

    await expect(rejectedHandler()(error)).rejects.toBe(error)

    expect(maintenanceLockoutMock).toHaveBeenCalledOnce()
    expect(sessionExpiredMock).not.toHaveBeenCalled()
  })

  it('leaves a plain 503 without the code alone - an ordinary server error is not maintenance', async () => {
    const error = { isAxiosError: true, response: { status: 503, data: {} } }

    await expect(rejectedHandler()(error)).rejects.toBe(error)

    expect(maintenanceLockoutMock).not.toHaveBeenCalled()
  })

  it('leaves a 503 with an unrelated code alone', async () => {
    const error = {
      isAxiosError: true,
      response: { status: 503, data: { code: 'SomeOtherError' } },
    }

    await expect(rejectedHandler()(error)).rejects.toBe(error)

    expect(maintenanceLockoutMock).not.toHaveBeenCalled()
  })

  it('still reports connectivity success for a 503 - the server did answer', async () => {
    const error = {
      isAxiosError: true,
      response: { status: 503, data: { code: 'MaintenanceModeError' } },
    }

    await expect(rejectedHandler()(error)).rejects.toBe(error)

    expect(reportSuccessMock).toHaveBeenCalledOnce()
    expect(reportFailureMock).not.toHaveBeenCalled()
  })
})
