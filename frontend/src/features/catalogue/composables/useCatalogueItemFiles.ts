import { computed, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useHostStore } from '@/core/host/stores/hostStore'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useConfirmDelete } from '@/shared/composables/useConfirmDelete'

import type { CatalogueFileRow } from '../components/CatalogueItemFilesCard.vue'

/** The fields of a stored item file the detail page reads. */
// eslint-disable-next-line no-restricted-syntax -- a structural constraint every item kind's file response must satisfy
export interface CatalogueItemFile {
  id: number
  file_name: string
  category: string
  mime_type?: string | null
  size_bytes?: number | null
  created?: string | null
}

/** The part of an item kind's files store the detail page uses. */
export interface CatalogueItemFilesStore<TFile extends CatalogueItemFile> {
  getFiles(itemId: number): TFile[]
  isLoading(itemId: number): boolean
  fetchFiles(itemId: number): Promise<void>
  refetchFiles(itemId: number): Promise<void>
  remove(itemId: number, fileId: number): Promise<void>
}

/**
 * The stored files of a catalogue item detail page: the Item card's mesh
 * and the Files card's rows, with the delete action of that card. The
 * picture is not a file; the page reads it with useShownPicture.
 *
 * The files are fetched once per id while storage is enabled, since
 * `fetchFiles` is idempotent. The Files card lists only `filesCardCategories`,
 * ordered by that list and then by file name, and labels each category from
 * `<categoryLabelPrefix>.<category>`.
 */
export function useCatalogueItemFiles<TFile extends CatalogueItemFile>(options: {
  itemId: Readonly<Ref<number>>
  item: Readonly<Ref<{ id: number } | null>>
  filesStore: CatalogueItemFilesStore<TFile>
  fetchBlob: (itemId: number, fileId: number) => Promise<Blob>
  filesCardCategories: readonly string[]
  categoryLabelPrefix: string
}) {
  const { t } = useI18n()
  const hostStore = useHostStore()
  const { withErrorToast } = useErrorToast()
  const { confirmDelete } = useConfirmDelete()
  const { item, filesStore } = options

  watch(
    options.itemId,
    (id) => {
      if (hostStore.storageEnabled) void filesStore.fetchFiles(id)
    },
    { immediate: true },
  )

  const itemFiles = computed(() => (item.value ? filesStore.getFiles(item.value.id) : []))

  const meshFile = computed(() => itemFiles.value.find((f) => f.category === 'mesh') ?? null)

  function fetchItemFileBlob(fileId: number): Promise<Blob> {
    if (!item.value) return Promise.reject(new Error('No item loaded.'))
    return options.fetchBlob(item.value.id, fileId)
  }

  const filesCardRows = computed<CatalogueFileRow[]>(() => {
    const order = options.filesCardCategories
    return itemFiles.value
      .filter((f) => order.includes(f.category))
      .slice()
      .sort((a, b) => {
        const byCategory = order.indexOf(a.category) - order.indexOf(b.category)
        return byCategory !== 0 ? byCategory : a.file_name.localeCompare(b.file_name)
      })
      .map((f) => ({
        id: f.id,
        file_name: f.file_name,
        category: f.category,
        mimeType: f.mime_type,
        size: f.size_bytes,
        created: f.created,
      }))
  })

  function filesCategoryLabel(category: string): string {
    return t(`${options.categoryLabelPrefix}.${category}`)
  }

  const filesCardLoading = computed(() => (item.value ? filesStore.isLoading(item.value.id) : false))

  const deletingFileId = ref<number | null>(null)

  // The file is deleted for good, so the user confirms first. refetchFiles
  // bypasses the cache so the list shows server state.
  async function onDeleteFile(file: CatalogueFileRow): Promise<void> {
    if (!item.value || deletingFileId.value !== null) return
    const id = item.value.id
    if (!(await confirmDelete(file.file_name))) return
    deletingFileId.value = file.id
    try {
      await withErrorToast(
        async () => {
          await filesStore.remove(id, file.id)
          await filesStore.refetchFiles(id)
        },
        { summary: file.file_name, fallbackMessage: t('common.files.errors.delete') },
      )
    } finally {
      deletingFileId.value = null
    }
  }

  return {
    itemFiles,
    meshFile,
    fetchItemFileBlob,
    filesCardRows,
    filesCategoryLabel,
    filesCardLoading,
    deletingFileId,
    onDeleteFile,
  }
}
