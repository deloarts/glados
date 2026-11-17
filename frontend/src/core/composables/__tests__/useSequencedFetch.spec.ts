import { describe, it, expect, vi } from 'vitest'
import axios from 'axios'

import { useSequencedFetch, bumpFetchEpoch } from '../useSequencedFetch'

/**
 * A promise plus its resolve/reject, so a test can control exactly when a
 * given call settles instead of racing on real timers.
 */
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('useSequencedFetch', () => {
  it('returns the result and toggles loading around a single call', async () => {
    const fetcher = vi.fn<(id: number) => Promise<string>>().mockResolvedValue('result')
    const { loading, error, run } = useSequencedFetch(fetcher)

    const promise = run(1)
    expect(loading.value).toBe(true)

    const result = await promise
    expect(result).toBe('result')
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(fetcher).toHaveBeenCalledWith(1)
  })

  it('discards a slow response that resolves after a faster, later call', async () => {
    const slow = deferred<string>()
    const fast = deferred<string>()
    const fetcher = vi.fn<() => Promise<string>>()
    fetcher.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)

    const { loading, run } = useSequencedFetch(fetcher)

    const slowResult = run()
    const fastResult = run()

    // The fast call resolves first...
    fast.resolve('fast')
    expect(await fastResult).toBe('fast')
    expect(loading.value).toBe(false)

    // ...then the slow one finally lands. It must be discarded, not
    // overwrite the fast call's result, and must not flip loading back on.
    slow.resolve('slow')
    expect(await slowResult).toBeUndefined()
    expect(loading.value).toBe(false)
  })

  it('discards a slow rejection that lands after a faster call already succeeded', async () => {
    const slow = deferred<string>()
    const fast = deferred<string>()
    const fetcher = vi.fn<() => Promise<string>>()
    fetcher.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)

    const { error, run } = useSequencedFetch(fetcher)

    const slowResult = run()
    const fastResult = run()

    fast.resolve('fast')
    await fastResult
    expect(error.value).toBeNull()

    slow.reject(new Error('stale failure'))
    expect(await slowResult).toBeUndefined()
    // A superseded call's failure must not clobber the current success state.
    expect(error.value).toBeNull()
  })

  it('normalizes an axios error onto `error` and returns undefined', async () => {
    const axiosError = Object.assign(new Error('Request failed'), {
      isAxiosError: true,
      response: { data: { detail: 'Something went wrong' } },
    })
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)

    const fetcher = vi.fn<() => Promise<string>>().mockRejectedValue(axiosError)
    const { loading, error, run } = useSequencedFetch(fetcher)

    const result = await run()

    expect(result).toBeUndefined()
    expect(error.value).toBe('Something went wrong')
    expect(loading.value).toBe(false)

    vi.restoreAllMocks()
  })

  // A response that resolves after bumpFetchEpoch() (e.g. a logout
  // firing mid-flight) must be discarded like any other superseded call,
  // silently, with no error set, even though nothing about this call's own
  // requestId makes it "stale" (it's still the only/latest call this
  // instance ever made).
  it('discards a response that resolves after bumpFetchEpoch() is called, even though it is still the latest requestId', async () => {
    const inFlight = deferred<string>()
    const fetcher = vi.fn<() => Promise<string>>().mockReturnValue(inFlight.promise)
    const { loading, error, run } = useSequencedFetch(fetcher)

    const result = run()
    expect(loading.value).toBe(true)

    // Simulates resetAllStores() running while this request is still in
    // flight. See resetOnLogout.ts.
    bumpFetchEpoch()

    inFlight.resolve('stale-post-logout-data')

    expect(await result).toBeUndefined()
    expect(error.value).toBeNull()
    expect(loading.value).toBe(false)
  })

  it('discards a rejection that lands after bumpFetchEpoch() without setting error', async () => {
    const inFlight = deferred<string>()
    const fetcher = vi.fn<() => Promise<string>>().mockReturnValue(inFlight.promise)
    const { error, run } = useSequencedFetch(fetcher)

    const result = run()
    bumpFetchEpoch()
    inFlight.reject(new Error('stale failure after logout'))

    expect(await result).toBeUndefined()
    expect(error.value).toBeNull()
  })

  it('still returns a normal result for a call started after the epoch bump', async () => {
    const fetcher = vi.fn<() => Promise<string>>().mockResolvedValue('fresh')
    const { run } = useSequencedFetch(fetcher)

    bumpFetchEpoch()

    expect(await run()).toBe('fresh')
  })
})

describe('useSequencedFetch failed and invalidate', () => {
  it('sets failed for a non-API failure, where error stays null, and clears it on the next call', async () => {
    const fetcher = vi.fn<() => Promise<string>>()
    fetcher.mockRejectedValueOnce(new Error('boom')).mockReturnValueOnce(new Promise(() => {}))
    const { error, failed, run } = useSequencedFetch(fetcher)

    expect(await run()).toBeUndefined()
    expect(failed.value).toBe(true)
    expect(error.value).toBeNull()

    void run()
    expect(failed.value).toBe(false)
  })

  it('does not set failed for a superseded rejection', async () => {
    const slow = deferred<string>()
    const fetcher = vi.fn<() => Promise<string>>()
    fetcher.mockReturnValueOnce(slow.promise).mockResolvedValueOnce('fast')
    const { failed, run } = useSequencedFetch(fetcher)

    const slowResult = run()
    expect(await run()).toBe('fast')
    slow.reject(new Error('stale failure'))

    expect(await slowResult).toBeUndefined()
    expect(failed.value).toBe(false)
  })

  it('discards a call in flight when invalidated and stops loading', async () => {
    const inFlight = deferred<string>()
    const fetcher = vi.fn<() => Promise<string>>().mockReturnValue(inFlight.promise)
    const { loading, run, invalidate } = useSequencedFetch(fetcher)

    const result = run()
    invalidate()
    expect(loading.value).toBe(false)

    inFlight.resolve('stale')
    expect(await result).toBeUndefined()
    expect(loading.value).toBe(false)
  })

  it('clears failed when invalidated, so a stale call settling later does not report a failure', async () => {
    const stale = deferred<string>()
    const fetcher = vi.fn<() => Promise<string>>()
    fetcher.mockReturnValueOnce(stale.promise).mockRejectedValueOnce(new Error('boom'))
    const { failed, run, invalidate } = useSequencedFetch(fetcher)

    const staleResult = run()
    expect(await run()).toBeUndefined()
    expect(failed.value).toBe(true)

    invalidate()
    stale.resolve('stale')
    expect(await staleResult).toBeUndefined()
    expect(failed.value).toBe(false)
  })
})
