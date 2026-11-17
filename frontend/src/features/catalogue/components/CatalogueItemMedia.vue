<script setup lang="ts">
// The picture, mesh and drawing tiles of a catalogue item detail page's
// Item card. Kind-agnostic: the page resolves the picture shown and the
// files, and passes a fetchBlob bound to its kind's file API. Opening a
// preview is self-contained.
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import { useBlobObjectUrl } from '@/shared/composables/useBlobObjectUrl'
import { MESH_MIME_TYPES } from '@/core/utils/meshFile'
import type { ShownPicture } from '@/shared/pictures'

// Loads the three.js viewer only when a mesh tile renders.
const MeshViewer = defineAsyncComponent(() => import('@/core/components/MeshViewer.vue'))

export interface CatalogueMediaFile {
  id: number
  file_name: string
}

const props = defineProps<{
  /** The picture shown for the item, opened full size from the slot. */
  picture: ShownPicture | null
  meshFile: CatalogueMediaFile | null
  /** Fetches the raw bytes of a stored file. */
  fetchBlob: (fileId: number) => Promise<Blob>
  /**
   * Shown, and orbitable, when the item has no mesh file. Fetched with a
   * plain fetch, since there is no file id.
   */
  meshPlaceholderUrl?: string | null
  /** Only made items have a drawing. */
  drawingFile?: CatalogueMediaFile | null
}>()

const { t } = useI18n()

// Only a fallback; mesh detection checks the extension first.
const MESH_MIME_FALLBACK: string = MESH_MIME_TYPES[0]

// ── Mesh tile ────────────────────────────────────────────────────────────
// A real mesh file or, without one, the placeholder URL, resolved to one
// value so the loader has a single watch target.
type MeshSource =
  | { type: 'file'; id: number; fileName: string }
  | { type: 'placeholder'; url: string }

const meshSource = computed<MeshSource | null>(() => {
  if (props.meshFile) {
    return { type: 'file', id: props.meshFile.id, fileName: props.meshFile.file_name }
  }
  if (props.meshPlaceholderUrl) return { type: 'placeholder', url: props.meshPlaceholderUrl }
  return null
})

const meshBlob = ref<Blob | null>(null)
const meshLoading = ref(false)

watch(
  meshSource,
  async (source) => {
    meshBlob.value = null
    if (!source) return
    meshLoading.value = true
    try {
      meshBlob.value =
        source.type === 'file'
          ? await props.fetchBlob(source.id)
          : await fetch(source.url).then((r) => r.blob())
    } catch {
      meshBlob.value = null
    } finally {
      meshLoading.value = false
    }
  },
  { immediate: true },
)

// The fetched blob is handed to the preview dialog, so a placeholder tile
// is clickable without a second request.
const meshClickable = computed(() => !!meshBlob.value)

function placeholderFileName(url: string): string {
  try {
    const path = new URL(url, window.location.origin).pathname
    const base = path.split('/').pop()
    return base || t('catalogue.itemDetail.media.placeholderName')
  } catch {
    return t('catalogue.itemDetail.media.placeholderName')
  }
}

const meshDisplayName = computed(() => {
  const source = meshSource.value
  if (!source) return ''
  return source.type === 'file' ? source.fileName : placeholderFileName(source.url)
})

// The mesh tile is also an orbit surface, so a drag ending inside it is not
// a click.
let meshPointerStart: { x: number; y: number } | null = null

function onMeshPointerDown(event: PointerEvent): void {
  meshPointerStart = { x: event.clientX, y: event.clientY }
}

function onMeshClick(event: MouseEvent): void {
  const start = meshPointerStart
  meshPointerStart = null
  if (start && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 4) return
  openMesh()
}

function openMesh(): void {
  const source = meshSource.value
  const blob = meshBlob.value
  if (!source || !blob) return
  if (source.type === 'file') {
    openPreview(source.fileName, MESH_MIME_FALLBACK, () => props.fetchBlob(source.id))
  } else {
    openPreview(meshDisplayName.value, MESH_MIME_FALLBACK, () => Promise.resolve(blob))
  }
}

// ── Drawing tile ─────────────────────────────────────────────────────────
// The PDF drawing is previewed through an object URL in the browser viewer.

const { url: drawingUrl, loading: drawingLoading } = useBlobObjectUrl(
  () => props.drawingFile?.id ?? null,
  (fileId) => props.fetchBlob(fileId),
)

function openDrawing(): void {
  const file = props.drawingFile
  if (!file) return
  openPreview(file.file_name, 'application/pdf', () => props.fetchBlob(file.id))
}

// ── Picture tile (the default-slot thumbnail) ──────────────────────────────

function openImage(): void {
  const picture = props.picture
  if (!picture) return
  // Any image/* type routes to the image branch; the bytes decide rendering.
  openPreview(picture.name, 'image/*', picture.fetchImage)
}

// ── Preview dialog (shared by both tiles) ─────────────────────────────────

const previewFileName = ref('')
const previewMimeType = ref('')
const previewFetcher = ref<() => Promise<Blob>>(() =>
  Promise.reject(new Error('No file selected.')),
)
const showPreview = ref(false)
// Mounted lazily, so nothing heavy exists until something is opened.
const previewReady = ref(false)

function openPreview(fileName: string, mimeType: string, fetcher: () => Promise<Blob>): void {
  previewFileName.value = fileName
  previewMimeType.value = mimeType
  previewFetcher.value = fetcher
  previewReady.value = true
  showPreview.value = true
}
</script>

<template>
  <div class="item-media">
    <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a button only while there is something to open, the role and tabindex are bound to that -->
    <div
      class="thumb-box"
      :class="{ 'media-clickable': !!picture }"
      :role="picture ? 'button' : undefined"
      :tabindex="picture ? 0 : undefined"
      v-tooltip="
        picture ? t('catalogue.itemDetail.media.openFile', { name: picture.name }) : undefined
      "
      @click="openImage"
      @keydown.enter="openImage"
    >
      <slot />
    </div>

    <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a button only while there is something to open, the role and tabindex are bound to that -->
    <div
      v-if="meshLoading || meshBlob"
      class="media-tile"
      :class="{ 'media-clickable': meshClickable }"
      :role="meshClickable ? 'button' : undefined"
      :tabindex="meshClickable ? 0 : undefined"
      v-tooltip="
        meshClickable ? t('catalogue.itemDetail.media.openFile', { name: meshDisplayName }) : undefined
      "
      @pointerdown="onMeshPointerDown"
      @click="onMeshClick"
      @keydown.enter="openMesh"
    >
      <i v-if="meshLoading" class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      <MeshViewer v-else-if="meshBlob" :blob="meshBlob" />
    </div>

    <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a button only while there is something to open, the role and tabindex are bound to that -->
    <div
      v-if="drawingLoading || drawingUrl"
      class="media-tile media-tile--drawing"
      :class="{ 'media-clickable': !!drawingFile }"
      :role="drawingFile ? 'button' : undefined"
      :tabindex="drawingFile ? 0 : undefined"
      v-tooltip="
        drawingFile ? t('catalogue.itemDetail.media.openFile', { name: drawingFile.file_name }) : undefined
      "
      :aria-label="
        drawingFile ? t('catalogue.itemDetail.media.openFile', { name: drawingFile.file_name }) : undefined
      "
      @click="openDrawing"
      @keydown.enter="openDrawing"
    >
      <i v-if="drawingLoading" class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      <!-- Rendered at full size and scaled down, since the PDF viewer needs a
           usable viewport. Pointer events are off so the tile takes the click. -->
      <iframe
        v-else-if="drawingUrl"
        :src="`${drawingUrl}#toolbar=0&navpanes=0&scrollbar=0&view=FitV`"
        class="drawing-frame"
        :title="drawingFile?.file_name"
        tabindex="-1"
      />
    </div>

    <FilePreviewDialog
      v-if="previewReady"
      v-model:visible="showPreview"
      :filename="previewFileName"
      :mime-type="previewMimeType"
      :fetch-blob="previewFetcher"
    />
  </div>
</template>

<style scoped lang="scss">
.item-media {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  flex-shrink: 0;
}

.thumb-box {
  border-radius: var(--p-border-radius-sm);
}

.media-tile {
  width: 6rem;
  height: 6rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--p-border-radius-sm);
  border: 1px solid var(--p-content-border-color);
  overflow: hidden;
}

// The scaled iframe still claims its untransformed size in flow, so it is
// taken out of it and pinned to the tile's top-left corner.
.media-tile--drawing {
  position: relative;
  background: var(--p-content-hover-background);
}

// 30rem scaled by 0.22 is 6.6rem in a 6rem tile, so the offset re-centres
// the overhang. The overscan hides the viewer's dark margin; view=FitV crops
// the sides instead of letterboxing.
.drawing-frame {
  position: absolute;
  top: -0.3rem;
  left: -0.3rem;
  width: 30rem;
  height: 30rem;
  border: none;
  transform: scale(0.22);
  transform-origin: top left;
  pointer-events: none;
}

.media-clickable {
  cursor: pointer;

  &:hover {
    border-color: var(--p-primary-color);
  }

  &:hover :deep(.thumb-img),
  &:hover :deep(.thumb-empty) {
    border-color: var(--p-primary-color);
  }
}
</style>
