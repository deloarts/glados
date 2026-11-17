<script setup lang="ts">
// The Files card of a catalogue item detail page: one row per file with
// preview, download and delete. Uploading stays in the edit dialog. The page
// passes rows already filtered and sorted, a categoryLabel function and a
// fetchBlob bound to its kind's file API.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatBytes } from '@/core/utils/bytes'
import { formatDateOrDash } from '@/core/utils/dates'
import { isPreviewableFile } from '@/core/utils/meshFile'
import { downloadBlob } from '@/core/utils/downloadBlob'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import FileActionButtons from '@/shared/components/files/FileActionButtons.vue'
import EmptyState from '@/shared/components/EmptyState.vue'

/**
 * One table row. mimeType, size and created are optional; their columns
 * only render when the data has them.
 */
export interface CatalogueFileRow {
  id: number
  file_name: string
  category: string
  mimeType?: string | null
  size?: number | null
  created?: string | null
}

const props = withDefaults(
  defineProps<{
    files: CatalogueFileRow[]
    categoryLabel: (category: string) => string
    canEdit: boolean
    /** Fetches the raw bytes of a stored file. */
    fetchBlob: (fileId: number) => Promise<Blob>
    /** The file being removed, so only its row shows a spinner. */
    deleting?: number | null
    /** Derived from the files store's isLoading. */
    loading?: boolean
    /**
     * The shared files store swallows fetch failures, so nothing sets this
     * today.
     */
    error?: boolean
  }>(),
  { deleting: null, loading: false, error: false },
)

const emit = defineEmits<{ delete: [file: CatalogueFileRow] }>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

// Size and Uploaded only get a column when some row has the field.
const showSize = computed(() => props.files.some((f) => f.size != null))
const showUploaded = computed(() => props.files.some((f) => f.created != null))

const previewFile = ref<CatalogueFileRow | null>(null)
const showPreview = ref(false)

function openPreview(file: CatalogueFileRow): void {
  previewFile.value = file
  showPreview.value = true
}

function fetchPreviewBlob(): Promise<Blob> {
  const file = previewFile.value
  if (!file) return Promise.reject(new Error('No file selected.'))
  return props.fetchBlob(file.id)
}

async function onDownload(file: CatalogueFileRow): Promise<void> {
  downloadBlob(await props.fetchBlob(file.id), file.file_name)
}
</script>

<template>
  <Panel :header="t('catalogue.itemDetail.cards.files')">
    <div class="card-scroll-body">
      <div v-if="loading && files.length === 0" class="loading-state">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      </div>
      <div v-else-if="error" class="error-state">
        <i class="mdi mdi-alert-outline" aria-hidden="true" />
        {{ t('catalogue.itemDetail.sectionError') }}
      </div>
      <template v-else>
        <DataTable
          :value="files"
          size="small"
          :show-gridlines="isTableGridlinesEnabled"
          :striped-rows="isTableStripedEnabled"
        >
          <template #empty>
            <EmptyState :message="t('catalogue.itemDetail.files.empty')" />
          </template>
          <Column :header="t('catalogue.itemDetail.files.columns.category')" style="width: 8rem">
            <template #body="{ data }">{{ categoryLabel((data as CatalogueFileRow).category) }}</template>
          </Column>
          <Column field="file_name" :header="t('catalogue.itemDetail.files.columns.name')" />
          <Column v-if="showSize" :header="t('catalogue.itemDetail.files.columns.size')" style="width: 7rem">
            <template #body="{ data }">{{
              (data as CatalogueFileRow).size != null ? formatBytes((data as CatalogueFileRow).size!) : ''
            }}</template>
          </Column>
          <Column
            v-if="showUploaded"
            :header="t('catalogue.itemDetail.files.columns.uploaded')"
            style="width: 8rem"
          >
            <template #body="{ data }">{{ formatDateOrDash((data as CatalogueFileRow).created) }}</template>
          </Column>
          <Column style="width: 7rem">
            <template #body="{ data }">
              <FileActionButtons
                :previewable="
                  isPreviewableFile((data as CatalogueFileRow).file_name, (data as CatalogueFileRow).mimeType)
                "
                :can-edit="canEdit"
                :deleting="deleting === (data as CatalogueFileRow).id"
                @preview="openPreview(data as CatalogueFileRow)"
                @download="onDownload(data as CatalogueFileRow)"
                @delete="emit('delete', data as CatalogueFileRow)"
              />
            </template>
          </Column>
        </DataTable>
      </template>
    </div>

    <FilePreviewDialog
      v-if="previewFile"
      v-model:visible="showPreview"
      :filename="previewFile.file_name"
      :mime-type="previewFile.mimeType ?? 'application/octet-stream'"
      :fetch-blob="fetchPreviewBlob"
    />
  </Panel>
</template>

<style scoped lang="scss">
.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
  font-size: var(--font-size-2xl);
  color: var(--p-text-muted-color);
}

.error-state {
  padding: var(--space-5) 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
