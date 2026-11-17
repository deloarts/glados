<script setup lang="ts">
/**
 * File management for any entity that carries attachments. Everything
 * entity-specific arrives as data: the category specs, the store and a blob
 * fetcher. Storage never hands out a browser-fetchable URL, so every download,
 * preview and inline image goes through an authenticated per-file route.
 *
 * Files picked before the entity exists are staged locally; the parent calls
 * `flushPendingUploads(id)` once it has an id and closes only if that resolves
 * true. Failed uploads stay staged, keeping their error.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { downloadBlob } from '@/core/utils/downloadBlob'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import FilesMultiCategory from './FilesMultiCategory.vue'
import FilesSingletonSlot from './FilesSingletonSlot.vue'
import { useFileUploads } from './composables/useFileUploads'
import { useMeshPreview } from './composables/useMeshPreview'
import { useImagePreviewCache } from './composables/useImagePreviewCache'
import type { FilesStoreInstance } from '@/core/stores/createFilesStore'
import { useErrorToast } from '@/core/composables/useErrorToast'
import type { MultiCategorySpec, SectionFile, SingletonCategorySpec } from './fileCategorySpec'

const props = withDefaults(
  defineProps<{
    /** null while the parent entity has not been created yet. */
    itemId: number | null
    filesStore: FilesStoreInstance<SectionFile, string>
    /** Categories holding at most one file, rendered as slots in a grid. */
    singletons?: SingletonCategorySpec[]
    /** Categories that accumulate, rendered as lists. */
    multi?: MultiCategorySpec[]
    canEdit: boolean
    readonly?: boolean
    /** Omit where the surrounding context already says "files". */
    titleKey?: string
    /**
     * `stack` (default) puts categories below each other; `row` places
     * them side by side as wrapping cards.
     */
    multiLayout?: 'stack' | 'row'
    /** Fetches raw bytes for download and the previews. */
    fetchBlob: (itemId: number, fileId: number) => Promise<Blob>
    /**
     * Adds a camera upload to every multi category, for places where a photo
     * is the document, such as QA evidence.
     */
    allowCapture?: boolean
    /**
     * Why the user may not change the files, naming the missing permission.
     * While `canEdit` is false and this is set, the upload and delete
     * controls stay visible but disabled with this tooltip; without it they
     * are hidden.
     */
    missingHint?: string
  }>(),
  {
    singletons: () => [],
    multi: () => [],
    readonly: false,
    allowCapture: false,
    multiLayout: 'stack',
    missingHint: '',
  },
)

const { t } = useI18n()
const { toastOnError } = useErrorToast()

const files = computed(() => (props.itemId ? props.filesStore.getFiles(props.itemId) : []))
const loading = computed(() => (props.itemId ? props.filesStore.isLoading(props.itemId) : false))
const hasFiles = computed(() => files.value.length > 0)
const canEditFiles = computed(() => props.canEdit && !props.readonly)
// The edit controls show while editing is allowed, and disabled with the
// missing permission as their tooltip while only the permission is lacking.
const showEditControls = computed(() => !props.readonly && (props.canEdit || props.missingHint !== ''))
const editBlocked = computed(() => (props.canEdit ? '' : props.missingHint))
const actionsMissingHint = computed(() => (props.readonly ? '' : props.missingHint))

const previewFile = ref<SectionFile | null>(null)
const showPreview = ref(false)

// The first file of each category, which is the one a singleton slot shows.
const firstFileByCat = computed(() => {
  const byCat = new Map<string, SectionFile>()
  for (const file of files.value) {
    if (!byCat.has(file.category)) byCat.set(file.category, file)
  }
  return byCat
})

function fileForCat(cat: string): SectionFile | undefined {
  return firstFileByCat.value.get(cat)
}

function filesForCat(cat: string): SectionFile[] {
  return files.value.filter((f) => f.category === cat)
}

const {
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
} = useFileUploads({
  itemId: () => props.itemId,
  filesStore: () => props.filesStore,
  singletons: () => props.singletons,
  multi: () => props.multi,
  fileForCat,
})

defineExpose({ flushPendingUploads })

// Bypasses the cache, so the management view always shows server state.
onMounted(() => {
  if (props.itemId) props.filesStore.refetchFiles(props.itemId).catch(toastOnError())
})

onBeforeUnmount(() => {
  revokePendingPreviews()
  revokeImageUrls()
})

// ── Download / preview ─────────────────────────────────────────────

async function blobFor(f: SectionFile): Promise<Blob> {
  if (!props.itemId) throw new Error('No item id to fetch the file for.')
  return props.fetchBlob(props.itemId, f.id)
}

async function onDownload(f: SectionFile): Promise<void> {
  downloadBlob(await blobFor(f), f.file_name)
}

function openPreview(f: SectionFile): void {
  previewFile.value = f
  showPreview.value = true
}

function fetchPreviewBlob(): Promise<Blob> {
  if (!previewFile.value) return Promise.reject(new Error('No file selected.'))
  return blobFor(previewFile.value)
}

// ── Inline mesh preview ────────────────────────────────────────────

const meshCat = computed(() => props.singletons.find((s) => s.render === 'mesh')?.key ?? null)
const meshFile = computed(() => (meshCat.value ? fileForCat(meshCat.value) : undefined))
const { meshBlob, meshLoading } = useMeshPreview(meshFile, blobFor)

// ── Inline image preview ───────────────────────────────────────────

const imageCats = computed(
  () => new Set(props.singletons.filter((s) => s.render === 'image').map((s) => s.key)),
)

const { urls: imageBlobUrls, revokeAll: revokeImageUrls } = useImagePreviewCache(
  files,
  imageCats,
  blobFor,
)
</script>

<template>
  <div v-if="!readonly || hasFiles" class="item-files" :class="{ 'item-files-readonly': readonly }">
    <div v-if="titleKey || loading" class="files-header">
      <span v-if="titleKey" class="files-title">{{ t(titleKey) }}</span>
      <i v-if="loading" class="mdi mdi-loading mdi-spin files-loading-icon" aria-hidden="true" />
    </div>

    <div v-if="singletons.length" class="singleton-grid">
      <template v-for="(spec, idx) in singletons" :key="spec.key">
        <FilesSingletonSlot
          v-if="!readonly || fileForCat(spec.key)"
          :spec="spec"
          :file="fileForCat(spec.key)"
          :pending="pendingSingletons[idx] ?? null"
          :pending-preview-url="pendingPreviewUrls[idx] ?? null"
          :image-url="fileForCat(spec.key) ? imageBlobUrls.get(fileForCat(spec.key)!.id) : undefined"
          :mesh-blob="meshBlob"
          :mesh-loading="meshLoading"
          :uploading="uploadingCats.has(spec.key)"
          :error="uploadErrors.get(spec.key)"
          :can-edit="canEditFiles"
          :show-edit-controls="showEditControls"
          :edit-blocked="editBlocked"
          :missing-hint="actionsMissingHint"
          :deleting="!!fileForCat(spec.key) && deletingIds.has(fileForCat(spec.key)!.id)"
          @pick="onSingletonInput($event, spec.key)"
          @drop-file="handleFile($event, spec.key)"
          @remove-pending="removePendingSingleton(idx)"
          @preview="openPreview"
          @download="onDownload"
          @delete="onDelete"
        />
      </template>
    </div>

    <!-- Accumulating categories: one list each -->
    <div class="multi-group" :class="{ 'multi-group--row': multiLayout === 'row' }">
      <template v-for="spec in multi" :key="spec.key">
        <FilesMultiCategory
          v-if="!readonly || filesForCat(spec.key).length > 0"
          :spec="spec"
          :files="filesForCat(spec.key)"
          :pending="pendingForCat(spec.key)"
          :uploading="uploadingCats.has(spec.key)"
          :error="uploadErrors.get(spec.key)"
          :can-edit="canEditFiles"
          :show-edit-controls="showEditControls"
          :edit-blocked="editBlocked"
          :missing-hint="actionsMissingHint"
          :deleting-ids="deletingIds"
          :allow-capture="allowCapture"
          @pick="onMultiInput($event, spec.key)"
          @drop-file="handleFile($event, spec.key)"
          @remove-pending="removePendingMulti(spec.key, $event)"
          @preview="openPreview"
          @download="onDownload"
          @delete="onDelete"
        />
      </template>
    </div>

    <FilePreviewDialog
      v-if="previewFile"
      v-model:visible="showPreview"
      :filename="previewFile.file_name"
      :mime-type="previewFile.mime_type"
      :fetch-blob="fetchPreviewBlob"
    />
  </div>
</template>

<style scoped lang="scss">
.item-files {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-1) 0 var(--space-4);
}

.item-files-readonly {
  padding-top: var(--space-4);
  border-top: 1px solid var(--p-content-border-color);
}

.files-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.files-title {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.files-loading-icon {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

// ── Singleton grid ────────────────────────────────────────────────

.singleton-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: 14rem;
  gap: var(--space-3);
}

// ── Multi-file section ────────────────────────────────────────────

// `stack` (the default): a flex column with its own gap. This wrapper sits
// between `.item-files` (which has a gap of its own) and the `.multi-section`
// children, so without a gap here the categories touch with no separation:
// `.item-files`'s gap only applies between its own direct children, and this
// div is the direct child instead of the sections themselves.
.multi-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

// `row` lays the same divs out as a wrapping card grid instead, mirroring
// .singleton-grid's pattern for entities that use singleton slots.
// align-items: start stops a category with many files from stretch-sizing
// its emptier siblings on the same row.
.multi-group--row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  align-items: start;
  gap: var(--space-3);
}

// ── Shared by the slots and the lists ─────────────────────────────

// The slots and lists are child components, so the styles they share reach
// into them from here rather than being repeated in each.
.item-files {
  :deep(.accent-purple) {
    background: color-mix(in srgb, var(--p-purple-500) 10%, transparent);
    color: var(--p-purple-600);
  }
  :deep(.accent-blue) {
    background: color-mix(in srgb, var(--p-blue-500) 10%, transparent);
    color: var(--p-blue-600);
  }
  :deep(.accent-teal) {
    background: color-mix(in srgb, var(--p-teal-500) 10%, transparent);
    color: var(--p-teal-600);
  }
  :deep(.accent-orange) {
    background: color-mix(in srgb, var(--p-orange-500) 10%, transparent);
    color: var(--p-orange-600);
  }
  :deep(.accent-red) {
    background: color-mix(in srgb, var(--p-red-500) 10%, transparent);
    color: var(--p-red-600);
  }
  :deep(.accent-green) {
    background: color-mix(in srgb, var(--p-green-500) 10%, transparent);
    color: var(--p-green-600);
  }
  :deep(.accent-indigo) {
    background: color-mix(in srgb, var(--p-indigo-500) 10%, transparent);
    color: var(--p-indigo-600);
  }
  :deep(.accent-grey) {
    background: var(--p-content-hover-background);
    color: var(--p-text-muted-color);
  }

  :deep(.upload-status) {
    display: inline-flex;
    align-items: center;
  }

  // Keeps a text alternative in the accessibility tree for the loading icon,
  // without giving it any visual footprint next to the icon itself.
  :deep(.visually-hidden) {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
    border: 0;
  }

  :deep(.pdm-badge) {
    font-size: var(--font-size-xs);
    padding: 0 var(--space-2);
    text-transform: none;
  }

  :deep(.slot-error) {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-1) var(--space-2);
    font-size: var(--font-size-xs);
    color: var(--p-red-500);
    background: color-mix(in srgb, var(--p-red-500) 8%, transparent);
    border-top: 1px solid color-mix(in srgb, var(--p-red-500) 20%, transparent);
  }

  :deep(.slot-pending) {
    opacity: 0.75;
  }

  :deep(.slot-pending-hint) {
    padding: var(--space-1) var(--space-2) var(--space-1);
    font-size: var(--font-size-xs);
    font-style: italic;
    color: var(--p-text-muted-color);
  }

  :deep(.hidden-input) {
    display: none;
  }
}
</style>
