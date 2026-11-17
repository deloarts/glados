<script setup lang="ts">
// A horizontally scrolling row of file boxes for made-item and source-item
// files. The preview caches are keyed by file id and drop object URLs as soon
// as a file leaves the list, because the strip stays mounted for the whole
// machine page; shared useImagePreviewCache only ever grows.
import { defineAsyncComponent, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import { withMimeFallback } from '@/core/utils/blobMime'

import type { MachineStripFile } from '../types/machineFileStrip'

// Loads the three.js viewer only for mesh files.
const MeshViewer = defineAsyncComponent(() => import('@/core/components/MeshViewer.vue'))

const props = defineProps<{
  files: MachineStripFile[]
  fetchBlob: (file: MachineStripFile) => Promise<Blob>
}>()

// The root is a fragment, so a parent class is forwarded to the strip div
// explicitly.
defineOptions({ inheritAttrs: false })

// Unknown categories, and content categories while loading or after a failed
// fetch, fall back to a generic file icon.
const FILE_CATEGORY_ICON: Record<string, string> = {
  thumbnail: 'mdi-image-outline',
  image: 'mdi-image-outline',
  step: 'mdi-file-outline',
  mesh: 'mdi-cube-outline',
  drawing: 'mdi-file-document-outline',
  dxf: 'mdi-vector-square',
  pdf: 'mdi-file-pdf-box',
}

const IMAGE_CATEGORIES = new Set(['thumbnail', 'image'])
const PDF_CATEGORIES = new Set(['drawing', 'pdf'])

function isImageFile(file: MachineStripFile): boolean {
  return IMAGE_CATEGORIES.has(file.category)
}

function isPdfFile(file: MachineStripFile): boolean {
  return PDF_CATEGORIES.has(file.category)
}

function isMeshFile(file: MachineStripFile): boolean {
  return file.category === 'mesh'
}

const { t } = useI18n()

// ── Content previews ─────────────────────────────────────────────────────
// Images and PDFs need an object URL; the mesh viewer takes the Blob.
const previewUrls = ref(new Map<number, string>())
const previewLoading = ref(new Set<number>())
const previewFailed = ref(new Set<number>())

const meshBlobs = ref(new Map<number, Blob>())
const meshLoading = ref(new Set<number>())
const meshFailed = ref(new Set<number>())

async function loadPreviewUrl(file: MachineStripFile): Promise<void> {
  if (previewUrls.value.has(file.id) || previewLoading.value.has(file.id)) return
  previewLoading.value = new Set(previewLoading.value).add(file.id)
  try {
    const blob = await props.fetchBlob(file)
    const typed = isPdfFile(file) ? withMimeFallback(blob, 'application/pdf') : blob
    previewUrls.value = new Map(previewUrls.value).set(file.id, URL.createObjectURL(typed))
  } catch {
    previewFailed.value = new Set(previewFailed.value).add(file.id)
  } finally {
    const next = new Set(previewLoading.value)
    next.delete(file.id)
    previewLoading.value = next
  }
}

async function loadMeshBlob(file: MachineStripFile): Promise<void> {
  if (meshBlobs.value.has(file.id) || meshLoading.value.has(file.id)) return
  meshLoading.value = new Set(meshLoading.value).add(file.id)
  try {
    meshBlobs.value = new Map(meshBlobs.value).set(file.id, await props.fetchBlob(file))
  } catch {
    meshFailed.value = new Set(meshFailed.value).add(file.id)
  } finally {
    const next = new Set(meshLoading.value)
    next.delete(file.id)
    meshLoading.value = next
  }
}

// Revokes object URLs of files no longer in the list.
function revokeUnusedPreviewUrls(currentIds: Set<number>): void {
  const next = new Map(previewUrls.value)
  let changed = false
  for (const [id, url] of previewUrls.value) {
    if (currentIds.has(id)) continue
    URL.revokeObjectURL(url)
    next.delete(id)
    changed = true
  }
  if (changed) previewUrls.value = next
}

watch(
  () => props.files,
  (list) => {
    const currentIds = new Set(list.map((f) => f.id))
    revokeUnusedPreviewUrls(currentIds)
    // Mesh blobs can be megabytes and the strip stays mounted for a shift, so
    // drop the ones whose file left the list.
    if ([...meshBlobs.value.keys()].some((id) => !currentIds.has(id))) {
      meshBlobs.value = new Map([...meshBlobs.value].filter(([id]) => currentIds.has(id)))
    }
    for (const file of list) {
      if (isImageFile(file) || isPdfFile(file)) void loadPreviewUrl(file)
      else if (isMeshFile(file)) void loadMeshBlob(file)
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  previewUrls.value.forEach((url) => URL.revokeObjectURL(url))
})

function isLoading(file: MachineStripFile): boolean {
  return previewLoading.value.has(file.id) || meshLoading.value.has(file.id)
}

const previewFile = ref<MachineStripFile | null>(null)
const showPreview = ref(false)

function openFile(file: MachineStripFile): void {
  previewFile.value = file
  showPreview.value = true
}

// Non-previewable files still open; the dialog shows its own no-preview
// state.
function fetchPreviewBlob(): Promise<Blob> {
  const file = previewFile.value
  if (!file) return Promise.reject(new Error('No file selected.'))
  return props.fetchBlob(file)
}
</script>

<template>
  <div v-if="files.length" class="file-strip" v-bind="$attrs">
    <div
      v-for="file in files"
      :key="file.id"
      class="file-box"
      role="button"
      tabindex="0"
      v-tooltip.top="t('production.lots.detail.record.item.openFile', { name: file.file_name })"
      :aria-label="t('production.lots.detail.record.item.openFile', { name: file.file_name })"
      @click="openFile(file)"
      @keydown.enter="openFile(file)"
      @keydown.space.prevent="openFile(file)"
    >
      <i
        v-if="isLoading(file)"
        class="mdi mdi-loading mdi-spin"
        aria-hidden="true"
        data-testid="file-strip-loading"
      />

      <img
        v-else-if="isImageFile(file) && previewUrls.get(file.id)"
        :src="previewUrls.get(file.id)"
        class="file-box-image"
        :alt="file.file_name"
      />

      <MeshViewer
        v-else-if="isMeshFile(file) && meshBlobs.get(file.id)"
        :blob="meshBlobs.get(file.id)!"
      />

      <!-- Rendered at full size and scaled down, because the PDF viewer needs
           a usable viewport. Pointer events are off so the box takes the click. -->
      <iframe
        v-else-if="isPdfFile(file) && previewUrls.get(file.id)"
        :src="`${previewUrls.get(file.id)}#toolbar=0&navpanes=0&scrollbar=0&view=FitV`"
        class="file-box-pdf"
        :title="file.file_name"
        tabindex="-1"
      />

      <i
        v-else
        class="mdi file-box-icon"
        :class="FILE_CATEGORY_ICON[file.category] ?? 'mdi-file-outline'"
      />
    </div>
  </div>

  <FilePreviewDialog
    v-if="previewFile"
    v-model:visible="showPreview"
    :filename="previewFile.file_name"
    :mime-type="previewFile.mime_type"
    :fetch-blob="fetchPreviewBlob"
  />
</template>

<style scoped lang="scss">
.file-strip {
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  padding-bottom: var(--space-1);
}

.file-box {
  flex-shrink: 0;
  width: 8rem;
  height: 8rem;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--p-border-radius-sm);
  border: 1px solid var(--p-content-border-color);
  overflow: hidden;
  cursor: pointer;
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);

  &:hover {
    border-color: var(--p-primary-color);
    color: var(--p-primary-color);
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
}

.file-box-icon {
  font-size: var(--font-size-2xl);
}

.file-box-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

// 30rem scaled by 0.3 is 9rem in an 8rem box, so the offset re-centres the
// overhang. The overscan hides the viewer's dark margin; view=FitV crops the
// sides instead of letterboxing.
.file-box-pdf {
  position: absolute;
  top: -0.5rem;
  left: -0.5rem;
  width: 30rem;
  height: 30rem;
  border: none;
  transform: scale(0.3);
  transform-origin: top left;
  pointer-events: none;
}
</style>
