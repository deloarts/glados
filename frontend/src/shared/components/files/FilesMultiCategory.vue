<script setup lang="ts">
/**
 * One list of FilesSection, for a category that accumulates files: the
 * uploaded files with their actions, the files staged before the entity
 * exists, and the upload and camera triggers. The list owns its file inputs
 * and its drag highlight; picking or dropping a file is handed up. The header
 * accents, upload status and error styles are FilesSection's.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatBytes } from '@/core/utils/bytes'
import { isPreviewableFile } from '@/core/utils/meshFile'
import FileActionButtons from './FileActionButtons.vue'
import type { MultiCategorySpec, SectionFile } from './fileCategorySpec'

const props = defineProps<{
  spec: MultiCategorySpec
  files: SectionFile[]
  /** Picked before the entity exists, not uploaded yet. */
  pending: File[]
  uploading: boolean
  error: string | undefined
  canEdit: boolean
  /** Whether the triggers show, disabled while only a permission is missing. */
  showEditControls: boolean
  editBlocked: string
  missingHint: string
  deletingIds: Set<number>
  /** Adds a camera upload beside the file picker. */
  allowCapture: boolean
}>()

const emit = defineEmits<{
  pick: [event: Event]
  dropFile: [file: File]
  removePending: [index: number]
  preview: [file: SectionFile]
  download: [file: SectionFile]
  delete: [file: SectionFile]
}>()

const { t } = useI18n()

const input = ref<HTMLInputElement | null>(null)
// Separate from the file input: `capture` has to sit on the element itself,
// so the camera path needs its own input rather than a toggled attribute.
const captureInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)

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
    class="multi-section"
    :class="{ 'drag-over': dragOver }"
    @dragover="onDragOver"
    @dragenter="onDragEnter"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div class="multi-header" :class="`accent-${spec.accent}`">
      <span>{{ t(spec.labelKey) }}</span>
      <span v-if="uploading" class="upload-status" role="status" aria-live="polite">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
        <span class="visually-hidden">{{ t('common.files.uploading') }}</span>
      </span>
    </div>

    <div class="multi-list">
      <div v-for="f in files" :key="f.id" class="multi-row">
        <i :class="[spec.icon, `icon-${spec.accent}`]" class="multi-icon" aria-hidden="true" />
        <span class="multi-name" :title="f.file_name">{{ f.file_name }}</span>
        <Tag
          v-if="f.from_pdm"
          value="PDM"
          severity="info"
          class="pdm-badge"
          v-tooltip.focus="t('common.files.pdmBadgeTooltip')"
        />
        <span class="multi-size">{{ formatBytes(f.size_bytes) }}</span>
        <FileActionButtons
          :style="{ gap: '0.4rem' }"
          :previewable="isPreviewableFile(f.file_name, f.mime_type)"
          :can-edit="canEdit"
          :missing-hint="missingHint"
          :deleting="deletingIds.has(f.id)"
          :locked="!!f.from_pdm"
          :locked-tooltip="t('common.files.pdmLockedTooltip')"
          @preview="emit('preview', f)"
          @download="emit('download', f)"
          @delete="emit('delete', f)"
        />
      </div>

      <div v-for="(f, idx) in pending" :key="`pending-${idx}`" class="multi-row slot-pending">
        <i :class="[spec.icon, `icon-${spec.accent}`]" class="multi-icon" aria-hidden="true" />
        <span class="multi-name" :title="f.name">{{ f.name }}</span>
        <span class="multi-size">{{ formatBytes(f.size) }}</span>
        <span class="slot-pending-hint">{{ t('common.files.pendingHint') }}</span>
        <Button
          v-if="canEdit"
          icon="mdi mdi-close"
          size="small"
          text
          rounded
          severity="danger"
          v-tooltip.focus="t('common.files.removePending')"
          :aria-label="t('common.files.removePending')"
          @click="emit('removePending', idx)"
        />
      </div>

      <div
        v-if="showEditControls"
        class="multi-triggers"
        v-tooltip.top="editBlocked || undefined"
        data-testid="file-multi-triggers"
      >
        <button
          type="button"
          class="multi-upload-trigger"
          :disabled="!canEdit"
          @click="input?.click()"
        >
          <i class="mdi mdi-plus" aria-hidden="true" />
          <span>{{ t('common.files.dropOrUpload') }}</span>
        </button>
        <button
          v-if="allowCapture"
          type="button"
          class="multi-upload-trigger multi-capture-trigger"
          :disabled="!canEdit"
          @click="captureInput?.click()"
        >
          <i class="mdi mdi-camera-outline" aria-hidden="true" />
          <span>{{ t('common.files.takePicture') }}</span>
        </button>
      </div>
      <div v-else-if="!files.length" class="multi-empty">
        {{ t('common.files.noDocuments') }}
      </div>
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
      multiple
      @change="emit('pick', $event)"
    />
    <!-- capture="environment" asks for the rear camera; browsers with no
         camera fall back to the normal file picker, so this degrades
         rather than breaking. -->
    <input
      v-if="allowCapture"
      ref="captureInput"
      type="file"
      aria-hidden="true"
      tabindex="-1"
      class="hidden-input"
      accept="image/*"
      capture="environment"
      @change="emit('pick', $event)"
    />
  </div>
</template>

<style scoped lang="scss">
.multi-section {
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

.multi-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-1) var(--space-3);
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--p-content-border-color);
}

.multi-list {
  display: flex;
  flex-direction: column;
}

.multi-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2) var(--space-1) var(--space-3);
  font-size: var(--font-size-sm);
  border-bottom: 1px solid var(--p-content-border-color);

  &:last-child {
    border-bottom: none;
  }
  &:hover {
    background: var(--p-content-hover-background);
  }
}

.multi-icon {
  font-size: var(--font-size-md);
  flex-shrink: 0;
  color: var(--p-text-muted-color);

  &.icon-purple {
    color: var(--p-purple-500);
  }
  &.icon-blue {
    color: var(--p-blue-500);
  }
  &.icon-teal {
    color: var(--p-teal-500);
  }
  &.icon-orange {
    color: var(--p-orange-500);
  }
  &.icon-red {
    color: var(--p-red-500);
  }
  &.icon-green {
    color: var(--p-green-500);
  }
  &.icon-indigo {
    color: var(--p-indigo-500);
  }
}

.multi-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.multi-size {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.multi-empty {
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.multi-triggers {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.multi-capture-trigger {
  flex: 0 0 auto;
}

.multi-upload-trigger {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font: inherit;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  background: none;
  border: none;
  border-radius: var(--p-content-border-radius);
  text-align: left;
  cursor: pointer;
  transition: background 0.1s;

  &:hover:not(:disabled) {
    background: var(--p-content-hover-background);
    color: var(--p-primary-color);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  i {
    font-size: var(--font-size-md);
  }
}
</style>
