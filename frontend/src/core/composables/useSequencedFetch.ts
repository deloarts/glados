import { ref } from 'vue'

import { extractApiError } from '@/core/utils/errors'

/** Shared by every `useSequencedFetch` call in the app. */
let fetchEpoch = 0

/**
 * Invalidates every request in flight app-wide, so its response is
 * discarded even if it is still the latest of its store. Without it, a
 * refresh in flight during logout would refill a just-reset store with the
 * previous user's data. Called from resetAllStores().
 */
export function bumpFetchEpoch(): void {
  fetchEpoch++
}

/**
 * Wraps a list fetch with `loading`, a normalized `error` and sequencing:
 * only the most recently started call's result is returned, so a slow stale
 * response can never overwrite a newer one, and a bumped epoch discards it
 * too.
 *
 * Errors are swallowed because callers are mostly unawaited watchers. A
 * `run()` returning `undefined` failed when `error` is set, and was
 * otherwise superseded. `error` stays null for a failure that is not an API
 * error, so `failed` tells a failure apart for any cause: it is cleared when
 * a call starts and set when the latest call throws.
 *
 * `invalidate()` discards every call in flight without starting a new one,
 * for a caller that resets its state to empty instead of fetching.
 */
export function useSequencedFetch<TArgs extends unknown[], TResult>(
  fetcher: (...args: TArgs) => Promise<TResult>,
) {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const failed = ref(false)
  let latestRequestId = 0

  async function run(...args: TArgs): Promise<TResult | undefined> {
    const requestId = ++latestRequestId
    const requestEpoch = fetchEpoch
    loading.value = true
    failed.value = false

    try {
      const result = await fetcher(...args)
      if (requestId !== latestRequestId) return undefined
      if (requestEpoch !== fetchEpoch) return undefined
      error.value = null
      return result
    } catch (e) {
      if (requestId !== latestRequestId) return undefined
      if (requestEpoch !== fetchEpoch) return undefined
      error.value = extractApiError(e)
      failed.value = true
      return undefined
    } finally {
      if (requestId === latestRequestId) loading.value = false
    }
  }

  function invalidate(): void {
    latestRequestId++
    loading.value = false
    failed.value = false
  }

  return { loading, error, failed, run, invalidate }
}
