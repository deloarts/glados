<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import EmptyState from '@/shared/components/EmptyState.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import { deleteMeetingFile, fetchMeetingFileBlob, renameMeetingFile, uploadMeetingFile } from '../api/meetingsApi'
import type { MeetingFileResponse, MeetingResponse } from '../types/meetingResponse'

/**
 * The Documents card: the images and PDFs of the meeting, those pasted into
 * a card among them, with upload, preview, rename and delete. Deleting a file
 * removes it from storage; an image a card still shows then shows as its
 * alt text.
 */
const props = defineProps<{
  meeting: MeetingResponse
  canWrite: boolean
  writeBlocked: string
}>()

const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()

const fileInput = useTemplateRef<HTMLInputElement>('fileInput')
const uploading = ref(false)
const dragging = ref(false)
const preview = ref<MeetingFileResponse | null>(null)
const renamingId = ref<number | null>(null)
const newName = ref('')
const renaming = ref(false)
const previewVisible = ref(false)

const editable = computed(() => props.meeting.valid)
const canUpload = computed(() => editable.value && props.canWrite)
const files = computed(() => props.meeting.files)

function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function iconOf(file: MeetingFileResponse): string {
  return file.category === 'image' ? 'mdi mdi-file-image-outline' : 'mdi mdi-file-pdf-box'
}

async function upload(list: FileList | File[] | null | undefined): Promise<void> {
  const picked = [...(list ?? [])]
  if (!picked.length || !canUpload.value) return
  uploading.value = true
  try {
    for (const file of picked) {
      try {
        await uploadMeetingFile(props.meeting.id, file)
        toast.success(file.name, t('meetings.documents.uploaded'))
      } catch (err) {
        toast.error(file.name, extractApiError(err) ?? t('meetings.errors.unknown'))
      }
    }
  } finally {
    uploading.value = false
    emit('changed')
  }
}

function onPicked(event: Event): void {
  const input = event.target as HTMLInputElement
  void upload(input.files)
  input.value = ''
}

function onDrop(event: DragEvent): void {
  dragging.value = false
  void upload(event.dataTransfer?.files)
}

/** Opens the file picker, for the Add File button of the controls bar. */
function pick(): void {
  fileInput.value?.click()
}

defineExpose({ pick })

function openPreview(file: MeetingFileResponse): void {
  preview.value = file
  previewVisible.value = true
}

function startRename(file: MeetingFileResponse): void {
  renamingId.value = file.id
  newName.value = file.file_name
}

// A new name keeps the file's extension, so the download still opens.
function withExtension(name: string, original: string): string {
  const dot = original.lastIndexOf('.')
  const extension = dot > 0 ? original.slice(dot) : ''
  return extension && !name.toLowerCase().endsWith(extension.toLowerCase()) ? `${name}${extension}` : name
}

async function saveRename(file: MeetingFileResponse): Promise<void> {
  const typed = newName.value.trim()
  const name = typed ? withExtension(typed, file.file_name) : ''
  if (!name || name === file.file_name) {
    renamingId.value = null
    return
  }
  renaming.value = true
  try {
    await renameMeetingFile(props.meeting.id, file.id, name)
    toast.success(name, t('meetings.documents.renamed'))
    renamingId.value = null
    emit('changed')
  } catch (err) {
    toast.error(file.file_name, extractApiError(err) ?? t('meetings.errors.unknown'))
  } finally {
    renaming.value = false
  }
}

function askDelete(file: MeetingFileResponse): void {
  confirm.require({
    header: t('meetings.documents.deleteHeader'),
    message: t('meetings.documents.deleteConfirm', { name: file.file_name }),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary', text: true },
    acceptProps: { label: t('meetings.documents.delete'), severity: 'danger', icon: 'mdi mdi-delete-outline' },
    accept: () => void runDelete(file),
  })
}

async function runDelete(file: MeetingFileResponse): Promise<void> {
  try {
    await deleteMeetingFile(props.meeting.id, file.id)
    toast.success(file.file_name, t('meetings.documents.deleted'))
    emit('changed')
  } catch (err) {
    toast.error(file.file_name, extractApiError(err) ?? t('meetings.errors.unknown'))
  }
}
</script>

<template>
  <SectionCard :title="t('meetings.documents.title')" icon="mdi-folder-open-outline" data-testid="meeting-documents-card">
    <template #title-end>
      <Tag v-if="files.length" :value="String(files.length)" severity="secondary" />
    </template>

    <ul v-if="files.length" class="file-list">
      <li v-for="file in files" :key="file.id" class="file-row">
        <i :class="iconOf(file)" aria-hidden="true" />
        <form v-if="renamingId === file.id" class="file-rename" @submit.prevent="saveRename(file)">
          <InputText
            v-model="newName"
            size="small"
            maxlength="255"
            :aria-label="t('meetings.documents.newName')"
            class="file-rename-input"
            data-testid="meeting-file-rename-input"
            @keydown.escape.stop="renamingId = null"
          />
          <Button
            type="button"
            icon="mdi mdi-close"
            size="small"
            severity="secondary"
            text
            :aria-label="t('common.cancel')"
            @click="renamingId = null"
          />
          <Button
            type="submit"
            icon="mdi mdi-check"
            size="small"
            severity="secondary"
            text
            :loading="renaming"
            :aria-label="t('meetings.documents.saveName')"
            data-testid="meeting-file-rename-save"
          />
        </form>
        <span v-else class="file-name">
          <button type="button" class="file-link" :title="file.file_name" @click="openPreview(file)">
            {{ file.file_name }}
          </button>
          <small v-if="file.card_id" class="text-muted">{{ t('meetings.documents.inCard') }}</small>
        </span>
        <small v-if="renamingId !== file.id" class="text-muted file-size">{{ sizeLabel(file.size_bytes) }}</small>
        <span v-if="editable && renamingId !== file.id" v-tooltip.top="writeBlocked || t('meetings.documents.rename')">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canWrite"
            :aria-label="t('meetings.documents.renameFile', { name: file.file_name })"
            :data-testid="`meeting-file-rename-${file.id}`"
            @click="startRename(file)"
          />
        </span>
        <span v-if="editable && renamingId !== file.id" v-tooltip.top="writeBlocked || undefined">
          <Button
            icon="mdi mdi-delete-outline"
            size="small"
            severity="danger"
            text
            :disabled="!canWrite"
            :aria-label="t('meetings.documents.deleteFile', { name: file.file_name })"
            @click="askDelete(file)"
          />
        </span>
      </li>
    </ul>
    <EmptyState v-else icon="mdi mdi-folder-open-outline" :message="t('meetings.documents.empty')" />

    <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a drop zone; the upload button is its keyboard path. -->
    <div
      v-if="editable"
      class="drop-zone"
      :class="{ dragging }"
      @dragover.prevent="dragging = canUpload"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
    >
      <span v-tooltip.top="writeBlocked || undefined">
        <Button
          :label="t('meetings.documents.upload')"
          icon="mdi mdi-upload"
          size="small"
          severity="secondary"
          text
          :loading="uploading"
          :disabled="!canUpload"
          data-testid="meeting-documents-upload"
          @click="pick"
        />
      </span>
      <small class="hint">{{ t('meetings.documents.dropHint') }}</small>
    </div>
    <input
      ref="fileInput"
      type="file"
      accept="image/*,application/pdf"
      multiple
      hidden
      :aria-label="t('meetings.documents.upload')"
      @change="onPicked"
    />

    <FilePreviewDialog
      v-if="preview"
      v-model:visible="previewVisible"
      :filename="preview.file_name"
      :mime-type="preview.mime_type"
      :fetch-blob="() => fetchMeetingFileBlob(meeting.id, preview!.id)"
    />
  </SectionCard>
</template>

<style scoped lang="scss">
.file-rename {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex: 1 1 auto;
  min-width: 0;
}

.file-rename-input {
  flex: 1 1 auto;
  min-width: 0;
}

.file-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.file-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.file-name {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-width: 0;
}

.file-link {
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  &:hover {
    color: var(--p-primary-color);
    text-decoration: underline;
  }
}

.file-size {
  white-space: nowrap;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-2);
  padding: var(--space-2);
  border: 1px dashed var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);

  &.dragging {
    border-color: var(--p-primary-color);
  }
}
</style>
