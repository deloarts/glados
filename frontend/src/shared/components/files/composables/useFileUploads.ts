import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useConfirmDelete } from '@/shared/composables/useConfirmDelete'
import { scaleDownForUpload } from '@/core/utils/imageResize'
import type { FilesStoreInstance } from '@/core/stores/createFilesStore'
import type { MultiCategorySpec, SectionFile, SingletonCategorySpec } from '../fileCategorySpec'

/** What FilesSection hands in: its current props and the slot lookup. */
export interface FileUploadsOptions {
  itemId: () => number | null
  filesStore: () => FilesStoreInstance<SectionFile, string>
  singletons: () => SingletonCategorySpec[]
  multi: () => MultiCategorySpec[]
  /** The first file of a category, the one a singleton slot shows. */
  fileForCat: (cat: string) => SectionFile | undefined
}

/**
 * Uploads, deletes and the local staging of FilesSection. Files picked
 * before the entity exists are staged with a preview and uploaded by
 * `flushPendingUploads(id)` once the entity has an id; failed uploads stay
 * staged with their error. The upload, error and delete state is kept per
 * category and per file id, so each slot shows its own spinner and message.
 */
export function useFileUploads(options: FileUploadsOptions) {
  const { t } = useI18n()
  const { withErrorToast } = useErrorToast()
  const { confirmDelete } = useConfirmDelete()

  const uploadingCats = ref<Set<string>>(new Set())
  const uploadErrors = ref<Map<string, string>>(new Map())
  const deletingIds = ref<Set<number>>(new Set())

  // Files picked before the entity exists, uploaded once an id arrives.
  const pendingSingletons = ref<(File | null)[]>(options.singletons().map(() => null))
  const pendingPreviewUrls = ref<(string | null)[]>(options.singletons().map(() => null))
  const pendingMulti = ref<Map<string, File[]>>(new Map())

  function pendingForCat(cat: string): File[] {
    return pendingMulti.value.get(cat) ?? []
  }

  // ── File inputs ────────────────────────────────────────────────────

  function onSingletonInput(e: Event, cat: string): void {
    const input = e.target as HTMLInputElement
    const file = input.files?.[0]
    input.value = ''
    if (file) void handleFile(file, cat)
  }

  function onMultiInput(e: Event, cat: string): void {
    const input = e.target as HTMLInputElement
    const picked = [...(input.files ?? [])]
    input.value = ''
    for (const file of picked) void handleFile(file, cat)
  }

  // ── Staging ────────────────────────────────────────────────────────

  function revokePendingPreview(idx: number): void {
    const url = pendingPreviewUrls.value[idx]
    if (url) URL.revokeObjectURL(url)
    pendingPreviewUrls.value[idx] = null
  }

  function revokePendingPreviews(): void {
    pendingPreviewUrls.value.forEach((url) => url && URL.revokeObjectURL(url))
  }

  function stagePending(file: File, cat: string): void {
    if (options.multi().some((m) => m.key === cat)) {
      pendingMulti.value = new Map(pendingMulti.value).set(cat, [...pendingForCat(cat), file])
      return
    }
    const idx = options.singletons().findIndex((s) => s.key === cat)
    if (idx < 0) return
    revokePendingPreview(idx)
    pendingSingletons.value[idx] = file
    if (file.type.startsWith('image/')) {
      pendingPreviewUrls.value[idx] = URL.createObjectURL(file)
    }
  }

  function removePendingSingleton(idx: number): void {
    revokePendingPreview(idx)
    pendingSingletons.value[idx] = null
  }

  function removePendingMulti(cat: string, idx: number): void {
    pendingMulti.value = new Map(pendingMulti.value).set(
      cat,
      pendingForCat(cat).filter((_, i) => i !== idx),
    )
  }

  /**
   * Uploads everything staged while the entity had no id. Failures stay staged
   * with their error, so the parent can keep its dialog open. Returns false if
   * any upload failed.
   */
  async function flushPendingUploads(itemId: number): Promise<boolean> {
    let allUploaded = true

    for (const [idx, spec] of options.singletons().entries()) {
      const file = pendingSingletons.value[idx]
      if (!file) continue
      if (await doUpload(file, spec.key, itemId)) {
        pendingSingletons.value[idx] = null
        revokePendingPreview(idx)
      } else {
        allUploaded = false
      }
    }

    for (const spec of options.multi()) {
      const toFlush = pendingForCat(spec.key)
      const stillPending: File[] = []
      for (const file of toFlush) {
        if (!(await doUpload(file, spec.key, itemId))) {
          stillPending.push(file)
          allUploaded = false
        }
      }
      pendingMulti.value = new Map(pendingMulti.value).set(spec.key, stillPending)
    }

    return allUploaded
  }

  // ── Upload / delete ────────────────────────────────────────────────

  async function handleFile(file: File, cat: string): Promise<void> {
    const itemId = options.itemId()
    if (itemId) await doUpload(file, cat, itemId)
    else stagePending(file, cat)
  }

  async function prepare(file: File, spec: SingletonCategorySpec | undefined): Promise<File> {
    if (!spec?.downscaleTo || !file.type.startsWith('image/')) return file
    return scaleDownForUpload(file, spec.downscaleTo)
  }

  async function doUpload(file: File, cat: string, itemId: number): Promise<boolean> {
    uploadingCats.value = new Set([...uploadingCats.value, cat])
    const cleared = new Map(uploadErrors.value)
    cleared.delete(cat)
    uploadErrors.value = cleared

    try {
      const singletons = options.singletons()
      const spec = singletons.find((s) => s.key === cat)
      await options.filesStore().upload(itemId, await prepare(file, spec), cat)

      // Auto-promote: uploading a full-size image with no thumbnail yet also
      // fills the thumbnail slot, so a table row gets a picture for free.
      const thumbSpec = singletons.find((s) => s.key === 'thumbnail')
      if (cat === 'image' && thumbSpec && !options.fileForCat('thumbnail')) {
        try {
          await options.filesStore().upload(itemId, await prepare(file, thumbSpec), thumbSpec.key)
        } catch {
          /* size/type limit exceeded, skip */
        }
      }
      return true
    } catch (e) {
      const next = new Map(uploadErrors.value)
      next.set(cat, extractApiError(e) ?? t('common.files.errors.upload'))
      uploadErrors.value = next
      return false
    } finally {
      uploadingCats.value = new Set([...uploadingCats.value].filter((c) => c !== cat))
    }
  }

  // A stored file is deleted for good, so the user confirms first. A refusal
  // shows the server's reason instead of the generic error.
  async function onDelete(f: SectionFile): Promise<void> {
    const itemId = options.itemId()
    if (!itemId || deletingIds.value.has(f.id)) return
    if (!(await confirmDelete(f.file_name))) return
    deletingIds.value = new Set([...deletingIds.value, f.id])
    try {
      await withErrorToast(() => options.filesStore().remove(itemId, f.id), {
        summary: f.file_name,
        fallbackMessage: t('common.files.errors.delete'),
      })
    } finally {
      deletingIds.value = new Set([...deletingIds.value].filter((id) => id !== f.id))
    }
  }

  return {
    uploadingCats,
    uploadErrors,
    deletingIds,
    pendingSingletons,
    pendingPreviewUrls,
    pendingForCat,
    onSingletonInput,
    onMultiInput,
    handleFile,
    removePendingSingleton,
    removePendingMulti,
    revokePendingPreviews,
    flushPendingUploads,
    onDelete,
  }
}
