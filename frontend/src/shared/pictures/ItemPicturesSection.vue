<script setup lang="ts">
/**
 * Every picture of a made, bought or source item, one slot per source: the
 * photo a person uploads, the EPLAN Data Portal picture and the CAD
 * rendering from PDM. Each source keeps its own picture, so uploading a
 * photo never replaces the other two. The slot of the picture shown for the
 * item is marked; the order is the photo, then the Data Portal picture,
 * then the CAD rendering. Only the photo can be uploaded or deleted here.
 *
 * A photo picked before the item exists is staged; the parent calls
 * `flushPendingUpload(id)` once it has an id.
 */
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import { extractApiError } from '@/core/utils/errors'
import { scaleDownForUpload } from '@/core/utils/imageResize'
import { useConfirmDelete } from '@/shared/composables/useConfirmDelete'

import { PICTURE_SOURCES } from './api'
import type { ItemPicture, ItemPictureSource } from './api'
import type { ItemPicturesStoreInstance } from './createItemPicturesStore'

const props = withDefaults(
  defineProps<{
    /** null while the item has not been created yet. */
    itemId: number | null
    store: ItemPicturesStoreInstance
    canEdit: boolean
    readonly?: boolean
  }>(),
  { readonly: false },
)

const { t } = useI18n()
const { confirmDelete } = useConfirmDelete()

// Longest side a photo is scaled down to before the upload, far above what
// any view shows and well inside the backend's size limit.
const MAX_PHOTO_SIDE = 2400
const ACCEPT = 'image/jpeg,image/png,image/webp'

const SOURCE_ACCENTS: Record<ItemPictureSource, string> = {
  picture: 'accent-blue',
  data_portal: 'accent-teal',
  cad_rendering: 'accent-purple',
}

watch(
  () => props.itemId,
  (id) => {
    if (id !== null) void props.store.fetchPictures(id)
  },
  { immediate: true },
)

const pictures = computed<ItemPicture[]>(() =>
  props.itemId === null ? [] : props.store.getPictures(props.itemId),
)
const loading = computed(() => props.itemId !== null && props.store.isLoadingPictures(props.itemId))

// The photo slot is always offered for editing; the other two only show up
// once their writer has stored a picture.
const slots = computed(() =>
  PICTURE_SOURCES.map((source) => ({
    source,
    picture: pictures.value.find((p) => p.source === source) ?? null,
  })).filter((slot) => slot.picture || (slot.source === 'picture' && !props.readonly)),
)

// ── Slot images ──────────────────────────────────────────────────────

const imageUrls = reactive(new Map<number, string>())

watch(
  pictures,
  async (current) => {
    const ids = new Set(current.map((p) => p.id))
    for (const [id, url] of imageUrls) {
      if (!ids.has(id)) {
        URL.revokeObjectURL(url)
        imageUrls.delete(id)
      }
    }
    for (const picture of current) {
      if (imageUrls.has(picture.id) || props.itemId === null) continue
      try {
        const blob = await props.store.getBlob(props.itemId, picture.source, 'thumbnail')
        if (!imageUrls.has(picture.id)) imageUrls.set(picture.id, URL.createObjectURL(blob))
      } catch {
        // The slot shows its placeholder icon instead.
      }
    }
  },
  { immediate: true },
)

// ── Photo upload ─────────────────────────────────────────────────────

const fileInput = ref<HTMLInputElement | null>(null)
const captureInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const deleting = ref(false)
const uploadError = ref<string | null>(null)
const dragOver = ref(false)
const pending = ref<File | null>(null)
const pendingUrl = ref<string | null>(null)

const editable = computed(() => props.canEdit && !props.readonly)
const noPermission = computed(() =>
  props.canEdit ? undefined : t('common.pictures.noPermission'),
)

function setPending(file: File | null): void {
  if (pendingUrl.value) URL.revokeObjectURL(pendingUrl.value)
  pending.value = file
  pendingUrl.value = file ? URL.createObjectURL(file) : null
}

async function send(itemId: number, file: File): Promise<boolean> {
  uploading.value = true
  uploadError.value = null
  try {
    await props.store.upload(itemId, await scaleDownForUpload(file, MAX_PHOTO_SIDE))
    return true
  } catch (err) {
    uploadError.value = extractApiError(err) ?? t('common.files.errors.upload')
    return false
  } finally {
    uploading.value = false
  }
}

async function accept(file: File | undefined): Promise<void> {
  if (!file || !editable.value) return
  if (props.itemId === null) {
    setPending(file)
    return
  }
  await send(props.itemId, file)
}

function onInput(event: Event): void {
  const input = event.target as HTMLInputElement
  void accept(input.files?.[0])
  input.value = ''
}

function onDrop(event: DragEvent): void {
  event.preventDefault()
  dragOver.value = false
  void accept(event.dataTransfer?.files?.[0])
}

function onDragOver(event: DragEvent): void {
  if (!editable.value) return
  event.preventDefault()
  dragOver.value = true
}

// The photo is deleted for good, so the user confirms first.
async function onDelete(): Promise<void> {
  if (props.itemId === null || deleting.value) return
  if (!(await confirmDelete(t('common.pictures.photoName')))) return
  deleting.value = true
  uploadError.value = null
  try {
    await props.store.removePhoto(props.itemId)
  } catch (err) {
    uploadError.value = extractApiError(err) ?? t('common.pictures.errors.delete')
  } finally {
    deleting.value = false
  }
}

/** Uploads a staged photo once the item exists; true when nothing failed. */
async function flushPendingUpload(itemId: number): Promise<boolean> {
  const file = pending.value
  if (!file) return true
  const ok = await send(itemId, file)
  if (ok) setPending(null)
  return ok
}

defineExpose({ flushPendingUpload })

onBeforeUnmount(() => {
  setPending(null)
  for (const url of imageUrls.values()) URL.revokeObjectURL(url)
})

// ── Preview ──────────────────────────────────────────────────────────

const preview = ref<ItemPicture | null>(null)
const showPreview = ref(false)

function openPreview(picture: ItemPicture): void {
  preview.value = picture
  showPreview.value = true
}

function previewBlob(): Promise<Blob> {
  const picture = preview.value
  if (!picture || props.itemId === null) return Promise.reject(new Error('No picture selected.'))
  return props.store.getBlob(props.itemId, picture.source, 'image')
}
</script>

<template>
  <div v-if="slots.length || pending" class="item-pictures">
    <div class="pictures-header">
      <span class="pictures-title">{{ t('common.pictures.title') }}</span>
      <i v-if="loading" class="mdi mdi-loading mdi-spin pictures-loading" aria-hidden="true" />
    </div>

    <div class="picture-grid">
      <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a drop target for dragged files, the upload button is the keyboard path -->
      <div
        v-for="slot in slots"
        :key="slot.source"
        class="picture-slot"
        :class="{ 'drag-over': slot.source === 'picture' && dragOver }"
        @dragover="slot.source === 'picture' ? onDragOver($event) : undefined"
        @dragleave="dragOver = false"
        @drop="slot.source === 'picture' ? onDrop($event) : undefined"
      >
        <div class="slot-header" :class="SOURCE_ACCENTS[slot.source]">
          <span>{{ t(`common.pictures.sources.${slot.source}`) }}</span>
          <Tag
            v-if="slot.picture?.in_use"
            :value="t('common.pictures.shown')"
            severity="success"
            class="shown-badge"
            v-tooltip.focus="t('common.pictures.shownTooltip')"
          />
          <i v-if="slot.source === 'picture' && uploading" class="mdi mdi-loading mdi-spin" aria-hidden="true" />
        </div>

        <!-- Stored picture -->
        <template v-if="slot.picture">
          <button
            type="button"
            class="slot-image-wrap"
            :aria-label="t('common.files.preview')"
            @click="openPreview(slot.picture)"
          >
            <img
              v-if="imageUrls.get(slot.picture.id)"
              :src="imageUrls.get(slot.picture.id)"
              class="slot-image"
              :alt="t(`common.pictures.sources.${slot.source}`)"
            />
            <i v-else class="mdi mdi-image-outline slot-placeholder" aria-hidden="true" />
          </button>
          <div v-if="slot.source === 'picture' && !readonly" class="slot-actions">
            <Button
              icon="mdi mdi-upload-outline"
              size="small"
              text
              rounded
              severity="secondary"
              :disabled="!canEdit || uploading"
              v-tooltip.focus="noPermission ?? t('common.pictures.replace')"
              :aria-label="t('common.pictures.replace')"
              @click="fileInput?.click()"
            />
            <Button
              icon="mdi mdi-delete-outline"
              size="small"
              text
              rounded
              severity="danger"
              :disabled="!canEdit || deleting"
              :loading="deleting"
              v-tooltip.focus="noPermission ?? t('common.pictures.delete')"
              :aria-label="t('common.pictures.delete')"
              @click="onDelete"
            />
          </div>
          <div v-else-if="slot.source !== 'picture'" class="slot-note">
            {{ t(`common.pictures.origin.${slot.source}`) }}
          </div>
        </template>

        <!-- Staged photo, uploaded after saving -->
        <template v-else-if="pending && pendingUrl">
          <div class="slot-image-wrap slot-pending">
            <img :src="pendingUrl" class="slot-image" :alt="pending.name" />
          </div>
          <span class="slot-note">{{ t('common.files.pendingHint') }}</span>
          <div class="slot-actions">
            <Button
              icon="mdi mdi-close"
              size="small"
              text
              rounded
              severity="danger"
              v-tooltip.focus="t('common.files.removePending')"
              :aria-label="t('common.files.removePending')"
              @click="setPending(null)"
            />
          </div>
        </template>

        <!-- No photo yet -->
        <div v-else class="slot-empty" :class="{ 'drop-active': dragOver }">
          <i class="mdi mdi-camera-outline slot-empty-icon" aria-hidden="true" />
          <span>{{ t('common.pictures.dropOrUpload') }}</span>
          <div class="empty-actions">
            <Button
              :label="t('common.pictures.upload')"
              size="small"
              text
              severity="secondary"
              :disabled="!canEdit"
              :loading="uploading"
              v-tooltip.focus="noPermission"
              @click="fileInput?.click()"
            />
            <Button
              :label="t('common.files.takePicture')"
              icon="mdi mdi-camera-outline"
              size="small"
              text
              severity="secondary"
              :disabled="!canEdit || uploading"
              v-tooltip.focus="noPermission"
              @click="captureInput?.click()"
            />
          </div>
        </div>

        <div v-if="slot.source === 'picture' && uploadError" class="slot-error">
          <i class="mdi mdi-alert-circle-outline" aria-hidden="true" />
          {{ uploadError }}
        </div>
      </div>
    </div>

    <input ref="fileInput" type="file" aria-hidden="true" tabindex="-1" class="hidden-input" :accept="ACCEPT" @change="onInput" />
    <!-- capture="environment" asks for the rear camera; a browser without
         one opens the file picker instead. -->
    <input
      ref="captureInput"
      type="file"
      aria-hidden="true"
      tabindex="-1"
      class="hidden-input"
      accept="image/*"
      capture="environment"
      @change="onInput"
    />

    <FilePreviewDialog
      v-if="preview"
      v-model:visible="showPreview"
      :filename="t(`common.pictures.sources.${preview.source}`)"
      mime-type="image/*"
      :fetch-blob="previewBlob"
    />
  </div>
</template>

<style scoped lang="scss">
.item-pictures {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-1) 0 var(--space-4);
}

.pictures-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.pictures-title {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.pictures-loading {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.accent-blue {
  background: color-mix(in srgb, var(--p-blue-500) 10%, transparent);
  color: var(--p-blue-600);
}
.accent-teal {
  background: color-mix(in srgb, var(--p-teal-500) 10%, transparent);
  color: var(--p-teal-600);
}
.accent-purple {
  background: color-mix(in srgb, var(--p-purple-500) 10%, transparent);
  color: var(--p-purple-600);
}

.picture-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: 14rem;
  gap: var(--space-3);
}

.picture-slot {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1.5px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  overflow: hidden;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;

  &.drag-over {
    border-color: var(--p-primary-color);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--p-primary-color) 20%, transparent);
  }
}

.slot-header {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--p-content-border-color);
}

.shown-badge {
  margin-left: auto;
  font-size: var(--font-size-xs);
  padding: 0 var(--space-2);
  text-transform: none;
}

.slot-image-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  background: var(--p-content-hover-background);
  overflow: hidden;
  cursor: zoom-in;
}

.slot-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.slot-placeholder {
  font-size: var(--font-size-xl);
  color: var(--p-text-muted-color);
  opacity: 0.4;
}

.slot-pending {
  opacity: 0.75;
  cursor: default;
}

.slot-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-1);
  border-top: 1px solid var(--p-content-border-color);
}

.slot-note {
  padding: var(--space-1) var(--space-2);
  font-size: var(--font-size-xs);
  font-style: italic;
  color: var(--p-text-muted-color);
  border-top: 1px solid var(--p-content-border-color);
}

.slot-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-3) var(--space-2);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
  text-align: center;
  transition: background 0.12s;

  &.drop-active {
    background: color-mix(in srgb, var(--p-primary-color) 6%, transparent);
  }
}

.slot-empty-icon {
  font-size: var(--font-size-xl);
  opacity: 0.4;
}

.empty-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-1);
}

.slot-error {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--p-red-500);
  background: color-mix(in srgb, var(--p-red-500) 8%, transparent);
  border-top: 1px solid color-mix(in srgb, var(--p-red-500) 20%, transparent);
}

.hidden-input {
  display: none;
}
</style>
