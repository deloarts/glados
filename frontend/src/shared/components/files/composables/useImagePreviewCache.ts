import { ref, watch, type ComputedRef, type Ref } from 'vue'

interface CategoryFile {
  id: number
  category: string
}

/**
 * Caches object URLs for every file rendered inline as an `<img>` in
 * FilesSection, keyed by file id, and revokes them as files disappear from
 * the list or the component unmounts.
 *
 * Contrast `useMeshPreview`, which hands the viewer a `Blob` directly. An
 * `<img>` needs a `src` URL instead, so this owns its own cache rather than
 * sharing one pattern across both preview kinds.
 */
export function useImagePreviewCache<TFile extends CategoryFile>(
  files: Ref<TFile[]> | ComputedRef<TFile[]>,
  imageCategories: Ref<Set<string>> | ComputedRef<Set<string>>,
  fetchBlob: (file: TFile) => Promise<Blob>,
): { urls: Ref<Map<number, string>>; revokeAll: () => void } {
  const urls = ref<Map<number, string>>(new Map())

  async function load(f: TFile): Promise<void> {
    if (urls.value.has(f.id)) return
    try {
      const url = URL.createObjectURL(await fetchBlob(f))
      urls.value = new Map(urls.value).set(f.id, url)
    } catch {
      /* show broken image */
    }
  }

  watch(
    files,
    (list) => {
      for (const f of list) if (imageCategories.value.has(f.category)) void load(f)
    },
    { immediate: true },
  )

  function revokeAll(): void {
    urls.value.forEach((url) => URL.revokeObjectURL(url))
  }

  return { urls, revokeAll }
}
