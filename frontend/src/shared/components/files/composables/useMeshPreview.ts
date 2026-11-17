import { ref, watch, type ComputedRef, type Ref } from 'vue'

/**
 * Loads and caches the blob for FilesSection's inline 3D mesh viewer.
 *
 * A mesh slot is a singleton category, so at most one file is ever "the"
 * mesh preview at a time. Contrast `useImagePreviewCache`, which tracks
 * many files at once. Re-fetches only when the file's id changes, so
 * unrelated re-renders (e.g. another category uploading) don't re-trigger
 * the fetch.
 */
export function useMeshPreview<TFile extends { id: number }>(
  meshFile: ComputedRef<TFile | undefined>,
  fetchBlob: (file: TFile) => Promise<Blob>,
): { meshBlob: Ref<Blob | null>; meshLoading: Ref<boolean> } {
  const meshBlob = ref<Blob | null>(null)
  const meshLoading = ref(false)
  let meshFileId: number | null = null

  watch(
    meshFile,
    async (f) => {
      if (!f) {
        meshBlob.value = null
        meshFileId = null
        return
      }
      if (meshFileId === f.id) return
      meshFileId = f.id
      meshBlob.value = null
      meshLoading.value = true
      try {
        meshBlob.value = await fetchBlob(f)
      } catch {
        meshBlob.value = null
      } finally {
        meshLoading.value = false
      }
    },
    { immediate: true },
  )

  return { meshBlob, meshLoading }
}
