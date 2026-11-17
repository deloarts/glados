import { onScopeDispose, ref, watch } from 'vue'
import type { WatchSource } from 'vue'

import { withMimeFallback } from '@/core/utils/blobMime'

/**
 * Loads the file `source` points at into an object URL for an embedded
 * viewer, such as the PDF drawing tile of an item. A new key revokes the
 * previous URL and fetches again, a null key just clears it, and the URL is
 * revoked when the owning scope ends.
 *
 * Only the latest key's response is applied, so a slow answer for a file the
 * view has moved on from neither replaces the current drawing nor leaks an
 * object URL. A failure of the latest fetch is rethrown, so it still reaches
 * the app's error handler. `fetch` returns null when the file cannot be
 * fetched yet, which leaves the URL empty. A blob without a MIME type is
 * typed as `fallbackMime`.
 */
export function useBlobObjectUrl<TKey>(
  source: WatchSource<TKey | null | undefined>,
  fetch: (key: TKey) => Promise<Blob> | null,
  fallbackMime = 'application/pdf',
) {
  const url = ref<string | null>(null)
  const loading = ref(false)
  let latestRequestId = 0

  function revoke(): void {
    if (url.value) {
      URL.revokeObjectURL(url.value)
      url.value = null
    }
  }

  watch(
    source,
    async (key) => {
      const requestId = ++latestRequestId
      revoke()
      loading.value = false
      if (key === null || key === undefined) return
      const pending = fetch(key)
      if (!pending) return
      loading.value = true
      try {
        const blob = await pending
        if (requestId !== latestRequestId) return
        url.value = URL.createObjectURL(withMimeFallback(blob, fallbackMime))
      } catch (e) {
        if (requestId !== latestRequestId) return
        throw e
      } finally {
        if (requestId === latestRequestId) loading.value = false
      }
    },
    { immediate: true },
  )

  onScopeDispose(() => {
    latestRequestId++
    revoke()
  })

  return { url, loading }
}
