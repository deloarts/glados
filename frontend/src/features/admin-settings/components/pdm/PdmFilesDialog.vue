<script setup lang="ts">
// The admin "PDM files" dialog: every file the poller has seen in a watched
// folder and where it stands (ingested, conflict, missing or errored).
// pdm_file_snapshot has no live resource, so the list reloads only on the
// reload button, a filter change or a page change. The caller mounts it with
// v-if, so useServerTable's mount fetch loads it on open. A modal needs only
// one compact filter row, so plain controls replace the ControlsBar.
import { computed, inject, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useConfirm } from 'openvue/useconfirm'
import { RouterLink, routerKey } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { useServerTable } from '@/core/composables/useServerTable'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { extractApiError } from '@/core/utils/errors'
import { formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { TABLE_DEFAULT_ROWS } from '@/core/constants/table'
import { usePdmFilesStore } from '../../stores/pdmFilesStore'
import { kindLabel } from '../../utils/pdmKind'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { PdmFileKind, PdmFileSnapshot, PdmFileSyncState } from '../../types/adminSettingsTypes'

const { t } = useI18n()
const appToast = useAppToast()
const confirm = useConfirm()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { hasPermission } = usePermissions()
// Same defensive inject as BoughtItemDetailFields.vue: a spec that mounts
// this dialog standalone (and mountWithApp in general) does not install a
// router by default, a plain `useRouter()` would log an injection warning
// on every router-less mount.
const router = inject(routerKey, null)

const canWrite = computed(() => hasPermission(Permission.WRITE_SETTINGS))

const store = usePdmFilesStore()

const visible = defineModel<boolean>('visible', { required: true })

const syncStateOptions = computed<{ label: string; value: PdmFileSyncState | null }[]>(() => [
  { label: t('adminSettings.pdmFiles.filters.all'), value: null },
  { label: t('adminSettings.solidworksPdm.pdm.sync.status.states.pending'), value: 'pending' },
  {
    label: t('adminSettings.solidworksPdm.pdm.sync.status.states.ingested'),
    value: 'ingested',
  },
  { label: t('adminSettings.solidworksPdm.pdm.sync.status.states.skipped'), value: 'skipped' },
  { label: t('adminSettings.solidworksPdm.pdm.sync.status.states.missing'), value: 'missing' },
  {
    label: t('adminSettings.solidworksPdm.pdm.sync.status.states.conflict'),
    value: 'conflict',
  },
  { label: t('adminSettings.solidworksPdm.pdm.sync.status.states.error'), value: 'error' },
])

const kindOptions = computed<{ label: string; value: PdmFileKind | null }[]>(() => [
  { label: t('adminSettings.pdmFiles.filters.all'), value: null },
  { label: t('adminSettings.itemFields.madeSection'), value: 'made' },
  { label: t('adminSettings.itemFields.boughtSection'), value: 'bought' },
  {
    label: t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.exportedDocuments'),
    value: 'document',
  },
])

const { first, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: (page) => ({ skip: page.first, limit: page.rows }),
  fetch: (page) => store.refresh(page),
})

// Typed search debounces like every other server table; the two Select
// filters fetch immediately on change, same as AdminSettingsTabAudit's
// domain filter.
watch(() => store.search, resetAndFetchDebounced)

function onFilterChange(): void {
  resetAndFetch()
}

function syncStateSeverity(
  state: PdmFileSyncState,
): 'success' | 'info' | 'secondary' | 'warn' | 'danger' {
  if (state === 'ingested') return 'success'
  if (state === 'pending') return 'info'
  if (state === 'skipped') return 'secondary'
  if (state === 'missing') return 'warn'
  return 'danger' // conflict | error
}

// item_kind, not kind: a document row's own kind is `document`, and only
// item_kind says which catalogue its item lives in.
function itemRoute(row: PdmFileSnapshot): string | null {
  if (row.item_id === null || row.item_kind === null) return null
  return row.item_kind === 'made'
    ? `/catalogue/made-items/${row.item_id}`
    : `/catalogue/bought-items/${row.item_id}`
}

// ── Row actions ──────────────────────────────────────────────────────────

const retryingId = ref<number | null>(null)

async function onRetry(row: PdmFileSnapshot): Promise<void> {
  retryingId.value = row.id
  try {
    await store.retry(row.id)
    appToast.success(t('adminSettings.pdmFiles.retrySuccess'))
  } catch (err: unknown) {
    appToast.error(
      t('adminSettings.pdmFiles.retryFailed'),
      extractApiError(err) ?? t('adminSettings.errors.unknown'),
    )
  } finally {
    retryingId.value = null
  }
}

function onDismiss(row: PdmFileSnapshot): void {
  async function onAccept(): Promise<void> {
    try {
      await store.dismiss(row.id)
      appToast.success(t('adminSettings.pdmFiles.dismissSuccess'))
    } catch (err: unknown) {
      appToast.error(
        t('adminSettings.pdmFiles.dismissFailed'),
        extractApiError(err) ?? t('adminSettings.errors.unknown'),
      )
    }
  }

  confirm.require({
    message: t('adminSettings.pdmFiles.dismissConfirm', { name: row.name }),
    header: t('adminSettings.pdmFiles.dismiss'),
    icon: 'mdi mdi-close-circle-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('adminSettings.pdmFiles.dismiss'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

// ── Error detail dialog ─────────────────────────────────────────────────

const errorDialogVisible = ref(false)
const errorDialogText = ref('')

function showError(row: PdmFileSnapshot): void {
  if (!row.last_error) return
  errorDialogText.value = row.last_error
  errorDialogVisible.value = true
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    maximizable
    :header="t('adminSettings.pdmFiles.dialogTitle')"
    :style="{ width: 'var(--dialog-width-full)', height: '80vh' }"
    content-class="pdm-files-dialog-content"
  >
    <div class="pdm-files-controls">
      <!-- Reloads this list only; the tab's "Synchronize with PDM" polls the vault. -->
      <Button
        :label="t('common.reload')"
        icon="mdi mdi-refresh"
        text
        severity="contrast"
        :loading="store.loading"
        @click="resetAndFetch"
      />
      <div class="filter-field">
        <label id="pdmf-sync-state-label" for="pdmf-sync-state">{{ t('adminSettings.pdmFiles.filters.syncState') }}</label>
        <Select
          class="filter-select select-placeholder-as-value"
          id="pdmf-sync-state"
          aria-labelledby="pdmf-sync-state-label"
          v-model="store.syncState"
          :options="syncStateOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('adminSettings.pdmFiles.filters.all')"
          @update:model-value="onFilterChange"
        />
      </div>
      <div class="filter-field">
        <label id="pdmf-kind-label" for="pdmf-kind">{{ t('adminSettings.pdmFiles.filters.kind') }}</label>
        <Select
          class="filter-select select-placeholder-as-value"
          id="pdmf-kind"
          aria-labelledby="pdmf-kind-label"
          v-model="store.kind"
          :options="kindOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('adminSettings.pdmFiles.filters.all')"
          @update:model-value="onFilterChange"
        />
      </div>
      <IconField>
        <InputIcon class="mdi mdi-magnify" />
        <InputText v-model="store.search" :placeholder="t('common.search')" />
      </IconField>
    </div>

    <DataTable
      class="pdm-files-table fixed-layout-table ellipsis-cells"
      :value="store.items"
      data-key="id"
      lazy
      :total-records="store.total"
      :rows="TABLE_DEFAULT_ROWS"
      :first="first"
      paginator
      scrollable
      scroll-height="flex"
      size="small"
      :loading="store.loading"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      @page="onPage"
    >
      <template #empty>
        <EmptyState :message="t('adminSettings.pdmFiles.noFiles')" />
      </template>

      <Column :header="t('adminSettings.pdmFiles.columns.actions')" style="width: 7rem">
        <template #body="{ data }: { data: PdmFileSnapshot }">
          <div class="row-actions">
            <Button
              icon="mdi mdi-refresh"
              size="small"
              severity="secondary"
              text
              :disabled="!canWrite"
              :loading="retryingId === data.id"
              v-tooltip.top="t('adminSettings.pdmFiles.retry')"
              :aria-label="t('adminSettings.pdmFiles.retry')"
              @click="onRetry(data)"
            />
            <Button
              icon="mdi mdi-close-circle-outline"
              size="small"
              severity="danger"
              text
              :disabled="!canWrite"
              v-tooltip.top="t('adminSettings.pdmFiles.dismiss')"
              :aria-label="t('adminSettings.pdmFiles.dismiss')"
              @click="onDismiss(data)"
            />
          </div>
        </template>
      </Column>

      <Column :header="t('adminSettings.pdmFiles.columns.syncStatus')" style="width: 9rem">
        <template #body="{ data }: { data: PdmFileSnapshot }">
          <Tag
            :severity="syncStateSeverity(data.sync_state)"
            :value="t(`adminSettings.solidworksPdm.pdm.sync.status.states.${data.sync_state}`)"
          />
        </template>
      </Column>

      <Column :header="t('adminSettings.pdmFiles.columns.file')" style="width: 14rem">
        <template #body="{ data }: { data: PdmFileSnapshot }">
          <div class="file-cell">
            <span class="file-name">{{ data.name }}</span>
            <span class="file-path" v-tooltip.top="data.path">{{ data.path }}</span>
          </div>
        </template>
      </Column>

      <Column :header="t('adminSettings.pdmFiles.columns.kind')" style="width: 9rem">
        <template #body="{ data }: { data: PdmFileSnapshot }">{{ kindLabel(data.kind) }}</template>
      </Column>

      <Column
        field="version"
        :header="t('adminSettings.pdmFiles.columns.version')"
        style="width: 6rem"
      />

      <Column :header="t('adminSettings.pdmFiles.columns.state')" style="width: 9rem">
        <template #body="{ data }: { data: PdmFileSnapshot }">{{ data.state }}</template>
      </Column>

      <Column :header="t('adminSettings.pdmFiles.columns.partNumber')" style="width: 10rem">
        <template #body="{ data }: { data: PdmFileSnapshot }">
          <RouterLink v-if="router && itemRoute(data)" :to="itemRoute(data)!" class="item-link">
            {{ data.part_number || getEmptyPlaceholder() }}
          </RouterLink>
          <span v-else>{{ data.part_number || getEmptyPlaceholder() }}</span>
        </template>
      </Column>
      <Column :header="t('adminSettings.pdmFiles.columns.revision')" style="width: 6rem">
        <template #body="{ data }: { data: PdmFileSnapshot }">
          {{ data.revision || getEmptyPlaceholder() }}
        </template>
      </Column>

      <Column :header="t('adminSettings.pdmFiles.columns.lastSeen')" style="width: 11rem">
        <template #body="{ data }: { data: PdmFileSnapshot }">
          {{ formatISODateTime(data.last_seen_at) }}
        </template>
      </Column>

      <!-- No fixed width: this is the one column that takes up the
           remaining table width, same convention as AdminSettingsTabAudit's
           unfixed "summary" column. -->
      <Column :header="t('adminSettings.pdmFiles.columns.error')">
        <template #body="{ data }: { data: PdmFileSnapshot }">
          <span
            v-if="data.last_error"
            class="error-cell"
            role="button"
            tabindex="0"
            v-tooltip.top="data.last_error"
            @click="showError(data)"
            @keydown.enter="showError(data)"
            @keydown.space.prevent="showError(data)"
            >{{ data.last_error }}</span
          >
          <span v-else>{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>
    </DataTable>
  </Dialog>

  <Dialog
    v-model:visible="errorDialogVisible"
    modal
    :header="t('adminSettings.pdmFiles.errorDialogTitle')"
    style="width: var(--dialog-width-md)"
  >
    <p class="error-dialog-text">{{ errorDialogText }}</p>
  </Dialog>
</template>

<style scoped lang="scss">
:global(.pdm-files-dialog-content) {
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: var(--space-6);
  overflow: hidden;
}

.pdm-files-table {
  flex: 1 1 auto;
  min-height: 0;

  // The sum of the declared column widths plus room for the one column that
  // declares none.
  --table-min-width: 91rem;
}

.pdm-files-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  flex: 0 0 auto;
}

.filter-field {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  label {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }

}

.filter-select {
  min-width: 12rem;
}

.file-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.file-name {
  font-size: var(--font-size-sm);
}

.file-path {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  // Bounded by the file column's own width, not a max-width here.
}

.item-link {
  color: var(--p-primary-color);
}

.error-cell {
  display: block;
  // The error column has no fixed width, so this truncates against whatever
  // is left of the table.
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.error-dialog-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
