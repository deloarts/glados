import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from 'axios'

import { useConnectionStore } from '../connectionStore'

vi.mock('axios', async () => {
  const actual = await vi.importActual<typeof import('axios')>('axios')
  return {
    ...actual,
    default: { ...actual.default, get: vi.fn<typeof actual.default.get>() },
  }
})

const mockedGet = vi.mocked(axios.get)

/**
 * An axios error as it arrives when nothing came back at all: no
 * `response` property. Both a genuine network error and a timeout look like
 * this, which is exactly why one of them alone must not mean "offline".
 */
function networkError(): Error {
  return Object.assign(new Error('Network Error'), {
    isAxiosError: true,
    code: 'ERR_NETWORK',
    toJSON: () => ({}),
  })
}

// The store registers its online/offline/visibilitychange listeners for the
// lifetime of the page and never tears them down, which is right for a
// singleton but means every store built in this file would otherwise still
// be listening in the next test, and answer events meant for its successor.
// Captured before anything is spied on so the delegation below can never
// chain through a previous test's spy.
const nativeWindowAdd = window.addEventListener.bind(window)
const nativeDocumentAdd = document.addEventListener.bind(document)

describe('connectionStore', () => {
  let registered: Array<[EventTarget, string, EventListenerOrEventListenerObject]> = []

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    mockedGet.mockReset()
    mockedGet.mockRejectedValue(networkError())

    registered = []
    for (const [target, native] of [
      [window, nativeWindowAdd],
      [document, nativeDocumentAdd],
    ] as const) {
      vi.spyOn(target, 'addEventListener').mockImplementation((type, listener, options) => {
        if (listener) registered.push([target, type, listener])
        native(type, listener, options)
      })
    }
  })

  afterEach(() => {
    for (const [target, type, listener] of registered) {
      target.removeEventListener(type, listener)
    }
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('starts online, and says nothing until something actually fails', () => {
    const store = useConnectionStore()

    expect(store.isOffline).toBe(false)
  })

  // The phone case: the first request after the browser is reopened has to
  // wake the radio, and one slow request is not an outage.
  it('does not go offline on a single failed request', () => {
    const store = useConnectionStore()

    store.reportFailure()

    expect(store.isOffline).toBe(false)
  })

  it('goes offline once two failures land in a row', () => {
    const store = useConnectionStore()

    store.reportFailure()
    store.reportFailure()

    expect(store.isOffline).toBe(true)
  })

  it('resets the failure count when a request succeeds in between', () => {
    const store = useConnectionStore()

    store.reportFailure()
    store.reportSuccess()
    store.reportFailure()

    expect(store.isOffline).toBe(false)
  })

  it('recovers as soon as any request succeeds', () => {
    const store = useConnectionStore()
    store.reportFailure()
    store.reportFailure()

    store.reportSuccess()

    expect(store.isOffline).toBe(false)
  })

  it('probes on a backoff while offline, and clears once the probe answers', async () => {
    const store = useConnectionStore()
    store.reportFailure()
    store.reportFailure()
    expect(mockedGet).not.toHaveBeenCalled()

    mockedGet.mockResolvedValue({ status: 200, data: { status: 'ok' } })
    await vi.advanceTimersByTimeAsync(3000)

    expect(mockedGet).toHaveBeenCalledOnce()
    expect(store.isOffline).toBe(false)
  })

  it('keeps probing while the server stays unreachable', async () => {
    const store = useConnectionStore()
    store.reportFailure()
    store.reportFailure()

    await vi.advanceTimersByTimeAsync(3000)
    expect(mockedGet).toHaveBeenCalledOnce()

    await vi.advanceTimersByTimeAsync(7000)
    expect(mockedGet).toHaveBeenCalledTimes(2)
    expect(store.isOffline).toBe(true)
  })

  // A 503 means the request reached a server, so the network path is up.
  // That is a different problem from being unreachable and not one the
  // footer speaks to.
  it('treats any HTTP response to the probe as back online', async () => {
    const store = useConnectionStore()
    store.reportFailure()
    store.reportFailure()

    mockedGet.mockRejectedValue(
      Object.assign(new Error('Service Unavailable'), {
        isAxiosError: true,
        response: { status: 503 },
        toJSON: () => ({}),
      }),
    )
    await vi.advanceTimersByTimeAsync(3000)

    expect(store.isOffline).toBe(false)
  })

  it('probes immediately on retryNow rather than waiting out the backoff', async () => {
    const store = useConnectionStore()
    store.reportFailure()
    store.reportFailure()

    mockedGet.mockResolvedValue({ status: 200, data: { status: 'ok' } })
    store.retryNow()
    await vi.advanceTimersByTimeAsync(0)

    expect(mockedGet).toHaveBeenCalledOnce()
    expect(store.isOffline).toBe(false)
  })

  it('goes offline immediately when the browser reports no network', () => {
    const store = useConnectionStore()

    window.dispatchEvent(new Event('offline'))

    expect(store.isOffline).toBe(true)
  })

  it('re-checks rather than assuming health when the browser reports network back', async () => {
    const store = useConnectionStore()
    window.dispatchEvent(new Event('offline'))

    mockedGet.mockResolvedValue({ status: 200, data: { status: 'ok' } })
    window.dispatchEvent(new Event('online'))
    await vi.advanceTimersByTimeAsync(0)

    // `navigator.onLine === true` only means an interface exists, so the
    // state must come from a request that actually landed.
    expect(mockedGet).toHaveBeenCalledOnce()
    expect(store.isOffline).toBe(false)
  })

  it('stops probing while the tab is hidden and picks straight back up on return', async () => {
    const store = useConnectionStore()
    store.reportFailure()
    store.reportFailure()

    const visibility = vi.spyOn(document, 'visibilityState', 'get')
    visibility.mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))

    await vi.advanceTimersByTimeAsync(60_000)
    expect(mockedGet).not.toHaveBeenCalled()

    visibility.mockReturnValue('visible')
    mockedGet.mockResolvedValue({ status: 200, data: { status: 'ok' } })
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)

    expect(mockedGet).toHaveBeenCalledOnce()
    expect(store.isOffline).toBe(false)
    visibility.mockRestore()
  })
})
