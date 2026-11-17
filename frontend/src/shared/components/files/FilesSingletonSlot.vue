<script setup lang="ts">
/**
 * One slot of FilesSection's grid, for a category that holds at most one
 * file: the uploaded file with its preview and actions, a file staged before
 * the entity exists, or an empty drop zone. The slot owns its file input and
 * its drag highlight; picking or dropping a file is handed up. The header
 * accents, upload status and error styles are FilesSection's.
 */
import { defineAsyncComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatBytes } from '@/core/utils/bytes'
import { isPreviewableFile } from '@/core/utils/meshFile'
import FileActionButtons from './FileActionButtons.vue'
import type { SectionFile, SingletonCategorySpec } from './fileCategorySpec'

const MeshViewer = defineAsyncComponent(() => import('@/core/components/MeshViewer.vue'))

const props = defineProps<{
  spec: SingletonCategorySpec
  file: SectionFile | undefined
  /** Picked before the entity exists, not uploaded yet. */
  pending: File | null
  pendingPreviewUrl: string | null
  /** The inline preview of an uploaded image. */
  imageUrl: string | undefined
  meshBlob: Blob | null
  meshLoading: boolean
  uploading: boolean
  error: string | undefined
  canEdit: boolean
  /** Whether the upload button shows, disabled while only a permission is missing. */
  showEditControls: boolean
  editBlocked: string
  missingHint: string
  deleting: boolean
}>()

const emit = defineEmits<{
  pick: [event: Event]
  dropFile: [file: File]
  removePending: []
  preview: [file: SectionFile]
  download: [file: SectionFile]
  delete: [file: SectionFile]
}>()

const { t } = useI18n()

const input = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)

function openPicker(): void {
  input.value?.click()
}

function onDragOver(e: DragEvent): void {
  e.preventDefault()
}

function onDragEnter(e: DragEvent): void {
  e.preventDefault()
  dragOver.value = true
}

function onDragLeave(e: DragEvent): void {
  const related = e.relatedTarget as Node | null
  if (related && (e.currentTarget as HTMLElement).contains(related)) return
  dragOver.value = false
}

function onDrop(e: DragEvent): void {
  e.preventDefault()
  dragOver.value = false
  if (!props.canEdit) return
  const file = e.dataTransfer?.files[0]
  if (file) emit('dropFile', file)
}

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/no-static-element-interactions -- a drop target for dragged files, the upload button is the keyboard path */
</script>

<template>
  <div
    class="singleton-slot"
    :class="{ 'drag-over': dragOver }"
    @dragover="onDragOver"
    @dragenter="onDragEnter"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div class="slot-header" :class="`accent-${spec.accent}`">
      <div class="slot-header-label">
        <span>{{ t(spec.labelKey) }}</span>
        <Tag
          v-if="file?.from_pdm"
          value="PDM"
          severity="info"
          class="pdm-badge"
          v-tooltip.focus="t('common.files.pdmBadgeTooltip')"
        />
      </div>
      <span v-if="uploading" class="upload-status" role="status" aria-live="polite">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
        <span class="visually-hidden">{{ t('common.files.uploading') }}</span>
      </span>
    </div>

    <!-- Occupied -->
    <template v-if="file">
      <div v-if="spec.render === 'image'" class="slot-image-wrap">
        <img :src="imageUrl" class="slot-image" :alt="file.file_name" />
      </div>
      <div v-else-if="spec.render === 'mesh'" class="slot-mesh-wrap">
        <i v-if="meshLoading" class="mdi mdi-loading mdi-spin slot-mesh-icon" aria-hidden="true" />
        <MeshViewer v-else-if="meshBlob" :blob="meshBlob" />
      </div>
      <div v-else class="slot-file-info">
        <i class="mdi mdi-file-outline slot-file-icon" aria-hidden="true" />
        <span class="slot-file-name" :title="file.file_name">
          {{ file.file_name }}
        </span>
        <span class="slot-file-size">{{ formatBytes(file.size_bytes) }}</span>
      </div>

      <FileActionButtons
        class="slot-actions"
        :previewable="isPreviewableFile(file.file_name, file.mime_type)"
        :can-edit="canEdit"
        :missing-hint="missingHint"
        :deleting="deleting"
        show-replace
        :locked="!!file?.from_pdm"
        :locked-tooltip="t('common.files.pdmLockedTooltip')"
        @preview="emit('preview', file)"
        @download="emit('download', file)"
        @replace="openPicker"
        @delete="emit('delete', file)"
      />
    </template>

    <!-- Staged, not yet uploaded -->
    <template v-else-if="pending">
      <div v-if="pendingPreviewUrl" class="slot-image-wrap slot-pending">
        <img :src="pendingPreviewUrl" class="slot-image" :alt="pending.name" />
      </div>
      <div v-else class="slot-file-info slot-pending">
        <i class="mdi mdi-file-outline slot-file-icon" aria-hidden="true" />
        <span class="slot-file-name" :title="pending.name">
          {{ pending.name }}
        </span>
        <span class="slot-file-size">{{ formatBytes(pending.size) }}</span>
      </div>
      <span class="slot-pending-hint">{{ t('common.files.pendingHint') }}</span>
      <div v-if="canEdit" class="slot-actions">
        <Button
          icon="mdi mdi-upload-outline"
          size="small"
          text
          rounded
          severity="secondary"
          :disabled="uploading"
          v-tooltip.focus="t('common.files.replaceHint')"
          :aria-label="t('common.files.replaceHint')"
          @click="openPicker"
        />
        <Button
          icon="mdi mdi-close"
          size="small"
          text
          rounded
          severity="danger"
          :disabled="uploading"
          v-tooltip.focus="t('common.files.removePending')"
          :aria-label="t('common.files.removePending')"
          @click="emit('removePending')"
        />
      </div>
    </template>

    <!-- Empty: drop zone -->
    <div v-else class="slot-empty" :class="{ 'drop-active': dragOver }">
      <i class="mdi mdi-upload-outline slot-empty-icon" aria-hidden="true" />
      <span>{{ t('common.files.dropOrUpload') }}</span>
      <span v-if="showEditControls" v-tooltip.top="editBlocked || undefined">
        <Button
          :label="t('common.files.upload')"
          size="small"
          text
          severity="secondary"
          :disabled="!canEdit"
          :loading="uploading"
          data-testid="file-upload"
          @click="openPicker"
        />
      </span>
    </div>

    <div v-if="error" class="slot-error">
      <i class="mdi mdi-alert-circle-outline" aria-hidden="true" />
      {{ error }}
    </div>

    <input
      ref="input"
      type="file"
      aria-hidden="true"
      tabindex="-1"
      class="hidden-input"
      :accept="spec.accept"
      @change="emit('pick', $event)"
    />
  </div>
</template>

<style scoped lang="scss">
.singleton-slot {
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
  justify-content: space-between;
  padding: var(--space-1) var(--space-2);
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--p-content-border-color);
}

.slot-header-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.slot-image-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--p-content-hover-background);
  overflow: hidden;
}

.slot-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.slot-mesh-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}

.slot-mesh-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: var(--font-size-xl);
  color: var(--p-text-muted-color);
  opacity: 0.4;
}

.slot-file-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2) var(--space-1);
  font-size: var(--font-size-sm);
  flex: 1;
}

.slot-file-icon {
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.slot-file-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.slot-file-size {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.slot-actions {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-1) var(--space-1);
  border-top: 1px solid var(--p-content-border-color);
  gap: var(--space-1);
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
  cursor: default;
  transition: background 0.12s;

  &.drop-active {
    background: color-mix(in srgb, var(--p-primary-color) 6%, transparent);
  }
}

.slot-empty-icon {
  font-size: var(--font-size-xl);
  opacity: 0.4;
}
</style>
