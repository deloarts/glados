import { computed, onUnmounted, ref, type Ref } from 'vue'
import { watch } from 'vue'

/**
 * The minimum an entity's file record must expose for a thumbnail to be
 * resolved from it. Each feature's own file type is a superset of this.
 */
interface ThumbnailFile {
  id: number
  category: string
}

/**
 * Resolves an item's thumbnail to an `<img src>`, owning the blob-URL
 * lifecycle that goes with it.
 *
 * Shared by every per-entity thumbnail cell. The tricky parts (revoking the
 * previous object URL before creating the next, re-fetching when a recycled
 * DataTable row swaps to a different item, and releasing on unmount) are
 * easy to get subtly wrong, and were already drifting between copies.
 */
export function useThumbnailSrc<TFile extends ThumbnailFile>(opts: {
  itemId: () => number
  files: (itemId: number) => TFile[]
  /** Which of the item's files to show; the thumbnail without one. */
  pick?: (files: TFile[]) => TFile | undefined
  fetchFiles: (itemId: number) => void | Promise<void>
  /**
   * Fetches the raw bytes for the thumbnail. Storage never hands out a
   * browser-fetchable URL, so every caller goes through an authenticated
   * per-file download route.
   */
  fetchBlob: (itemId: number, fileId: number) => Promise<Blob>
}): Ref<string | null> {
  const thumbnail = computed(() => {
    const files = opts.files(opts.itemId())
    return opts.pick ? opts.pick(files) : files.find((f) => f.category === 'thumbnail')
  })

  const imgSrc = ref<string | null>(null)
  let ownedBlobUrl: string | null = null

  // Idempotent, the store skips items already loaded or in flight, and
  // coalesces whatever is left into one bulk request per tick, so a table of
  // these costs a single call rather than one per row. Watched rather than
  // called once, since a table row can be recycled onto a different item
  // without remounting this component.
  watch(opts.itemId, (id) => opts.fetchFiles(id), { immediate: true })

  watch(
    thumbnail,
    async (file, previous) => {
      // A reload of the files hands over equal records as new objects; the
      // picture shown is still the right one.
      if (file && ownedBlobUrl && file.id === previous?.id) return
      if (ownedBlobUrl) {
        URL.revokeObjectURL(ownedBlobUrl)
        ownedBlobUrl = null
      }
      if (!file) {
        imgSrc.value = null
        return
      }
      try {
        const blob = await opts.fetchBlob(opts.itemId(), file.id)
        ownedBlobUrl = URL.createObjectURL(blob)
        imgSrc.value = ownedBlobUrl
      } catch {
        imgSrc.value = null
      }
    },
    { immediate: true },
  )

  onUnmounted(() => {
    if (ownedBlobUrl) URL.revokeObjectURL(ownedBlobUrl)
  })

  return imgSrc
}
