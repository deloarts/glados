import { onScopeDispose, reactive, watch } from 'vue'

import { getDeviceImageBlob } from '../api/deviceImagesApi'

/**
 * Object URLs of device renderings, for the devices table and the detailed
 * overview. Each rendering is fetched once while `enabled` is true, a failed
 * fetch is tried again on the next change, and every URL is revoked when the
 * owning scope ends.
 */
export function useDeviceRenderings(options: {
  productId: () => number
  fileIds: () => (number | null)[]
  enabled?: () => boolean
}): { urlFor: (fileId: number | null) => string | null } {
  const urls = reactive(new Map<number, string>())
  const requested = new Set<number>()

  watch(
    [() => options.enabled?.() ?? true, options.fileIds],
    ([enabled, fileIds]) => {
      if (!enabled) return
      for (const fileId of fileIds) {
        if (fileId === null || requested.has(fileId)) continue
        requested.add(fileId)
        getDeviceImageBlob(options.productId(), fileId)
          .then((blob) => urls.set(fileId, URL.createObjectURL(blob)))
          .catch(() => requested.delete(fileId))
      }
    },
    { immediate: true },
  )

  onScopeDispose(() => {
    for (const url of urls.values()) URL.revokeObjectURL(url)
  })

  return { urlFor: (fileId) => (fileId === null ? null : (urls.get(fileId) ?? null)) }
}
