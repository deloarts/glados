<script setup lang="ts">
/**
 * File management for source items and products.
 *
 * Both carry the same three categories (a thumbnail, a full-size image and
 * accumulating documents), so one wrapper serves both; only the store and the
 * category label keys differ. Behaviour and appearance come from the shared
 * FilesSection, the same component the catalogue items use.
 */
import type { FilesStoreInstance } from '@/core/stores/createFilesStore'
import FilesSection from './FilesSection.vue'
import type { MultiCategorySpec, SingletonCategorySpec } from './fileCategorySpec'

// eslint-disable-next-line no-restricted-syntax -- a structural constraint every item kind's file response must satisfy
interface SectionFile {
  id: number
  file_name: string
  mime_type: string
  size_bytes: number
  category: string
}

const props = defineProps<{
  itemId: number
  filesStore: FilesStoreInstance<SectionFile, string>
  canEdit: boolean
  /** Why the user may not change the files; see FilesSection. */
  missingHint?: string
  /**
   * i18n prefix for the section title and category labels, e.g.
   * 'sourceItems.catalogue.files'.
   */
  i18nPrefix: string
  fetchBlob: (itemId: number, fileId: number) => Promise<Blob>
}>()

// accept values mirror the backend's per-category validation. Neither entity
// has CAD slots: a source item is raw stock, and a product's geometry lives on
// the made items beneath it.
const SINGLETONS: SingletonCategorySpec[] = [
  {
    key: 'thumbnail',
    labelKey: `${props.i18nPrefix}.categories.thumbnail`,
    accent: 'purple',
    accept: 'image/jpeg,image/png,image/webp',
    render: 'image',
    downscaleTo: 256,
  },
  {
    key: 'image',
    labelKey: `${props.i18nPrefix}.categories.image`,
    accent: 'blue',
    accept: 'image/jpeg,image/png,image/webp',
    render: 'image',
  },
]

const MULTI: MultiCategorySpec[] = [
  {
    key: 'pdf',
    labelKey: `${props.i18nPrefix}.categories.pdf`,
    accent: 'red',
    accept: 'application/pdf',
    icon: 'mdi mdi-file-pdf-box',
  },
]
</script>

<template>
  <FilesSection
    :item-id="itemId"
    :files-store="filesStore"
    :singletons="SINGLETONS"
    :multi="MULTI"
    :can-edit="canEdit"
    :missing-hint="missingHint"
    :title-key="`${i18nPrefix}.title`"
    :fetch-blob="fetchBlob"
  />
</template>
